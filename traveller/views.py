# traveller/views.py
import json
import logging
from decimal import Decimal
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Avg
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.templatetags.static import static

# ReportLab imports
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# xhtml2pdf imports
from django.template.loader import get_template
from xhtml2pdf import pisa

# Razorpay imports
import razorpay

# Local app imports
from bus_owner.models import Bus, BusSchedule, RouteStop
from .models import Booking, ConcessionApplication, ConcessionDetail
from reviews.models import AppReview, BusReview

# Logger configuration
logger = logging.getLogger(__name__)

# ============================================================
# TRAVELLER DASHBOARD
# ============================================================

@login_required
def traveller_dashboard(request):
    """Main dashboard for travellers"""
    user = request.user

    # Search logic
    query = request.GET.get('stop', '').strip()
    search_results = []

    if query:
        matching_stops = RouteStop.objects.filter(stop_name__icontains=query)
        if matching_stops.exists():
            route_ids = matching_stops.values_list('route_id', flat=True).distinct()
            search_results = BusSchedule.objects.filter(
                route_id__in=route_ids,
                bus__approved=True,
                active=True
            ).select_related('bus', 'route').order_by('departure_time')

    # Dashboard data
    buses = Bus.objects.filter(approved=True)
    bookings = Booking.objects.filter(traveller=user).order_by('-booking_date')
    total_bookings = bookings.count()

    concession = ConcessionApplication.objects.filter(traveller=user).order_by('-applied_on').first()
    concession_detail = None
    if concession and concession.status == "Approved":
        concession_detail = ConcessionDetail.objects.filter(application=concession).first()

    # App reviews
    reviews = AppReview.objects.order_by("-created_at")[:6]

    context = {
        'user': user,
        'query': query,
        'search_results': search_results,
        'buses': buses,
        'bookings': bookings,
        'total_bookings': total_bookings,
        'concession': concession,
        'concession_detail': concession_detail,
        'default_bus_img': static('images/default_bus.jpg'),
        'reviews': reviews,
    }

    return render(request, 'traveller/traveller_dashboard.html', context)


# ============================================================
# BUS SCHEDULES & BOOKING
# ============================================================

@login_required
def view_schedules(request, bus_id):
    """View schedules for a specific bus"""
    bus = get_object_or_404(Bus, id=bus_id, approved=True)
    schedules = BusSchedule.objects.filter(bus=bus)

    if not schedules.exists():
        messages.warning(request, "No schedules found for this bus.")
        return redirect("traveller_dashboard")

    reviews = BusReview.objects.filter(bus=bus).select_related("traveller")
    avg_rating = reviews.aggregate(Avg("rating"))["rating__avg"]

    return render(request, "traveller/view_schedules.html", {
        "bus": bus,
        "schedules": schedules,
        "reviews": reviews,
        "avg_rating": avg_rating,
    })


from datetime import timedelta
# Add this import at the top
from .utils import is_segment_available, calculate_segment_fare, get_available_segments
from .models import SeatSegment
from django.db import transaction

@login_required
def book_bus(request, schedule_id):
    schedule = get_object_or_404(
        BusSchedule.objects.select_related("bus", "route"),
        id=schedule_id
    )

    bus = schedule.bus
    route = schedule.route
    photos = bus.photos.all()

    stops = list(route.stops.all().order_by("order"))
    total_stops = len(stops)
    
    PRICE_PER_STOP = Decimal("5.00")

    # Get all seat segments for this schedule
    all_segments = SeatSegment.objects.filter(
        schedule=schedule,
        is_active=True
    ).select_related('from_stop', 'to_stop')
    
    # Create a map of seat availability
    seat_availability_map = {}
    for seat_num in range(1, bus.total_seats + 1):
        available_segments = get_available_segments(schedule.id, seat_num, total_stops)
        seat_availability_map[seat_num] = {
            'available': len(available_segments) > 0,
            'available_segments': available_segments
        }
    
    # Calculate available seats count (seats with at least one available segment)
    available_seats = sum(1 for seat in seat_availability_map.values() if seat['available'])
    seat_range = range(1, bus.total_seats + 1)

    if request.method == "POST":
        seat_number = int(request.POST.get("seat_number"))
        from_stop_id = request.POST.get("from_stop")
        to_stop_id = request.POST.get("to_stop")
        payment_id = request.POST.get("razorpay_payment_id")

        if not all([seat_number, from_stop_id, to_stop_id, payment_id]):
            messages.error(request, "All fields including payment are required.")
            return redirect("book_bus", schedule_id=schedule.id)

        from_stop = get_object_or_404(RouteStop, id=from_stop_id)
        to_stop = get_object_or_404(RouteStop, id=to_stop_id)

        if from_stop.order >= to_stop.order:
            messages.error(request, "Invalid stops selected.")
            return redirect("book_bus", schedule_id=schedule.id)

        # Check if this specific segment is available
        if not is_segment_available(schedule.id, seat_number, from_stop.order, to_stop.order):
            messages.error(request, "This seat segment is no longer available.")
            return redirect("book_bus", schedule_id=schedule.id)

        # Calculate fare for this segment
        stops_travelled = to_stop.order - from_stop.order
        segment_fare = calculate_segment_fare(
            Decimal(schedule.fare), 
            from_stop.order, 
            to_stop.order, 
            PRICE_PER_STOP
        )

        try:
            client = razorpay.Client(auth=(
                settings.RAZORPAY_KEY_ID,
                settings.RAZORPAY_KEY_SECRET
            ))

            # Verify payment
            payment = client.payment.fetch(payment_id)

            if payment["status"] != "captured":
                messages.error(request, "Payment not captured.")
                return redirect("book_bus", schedule_id=schedule.id)

            with transaction.atomic():
                # Create the booking
                booking = Booking.objects.create(
                    traveller=request.user,
                    bus=bus,
                    schedule=schedule,
                    seat_number=seat_number,
                    from_stop=from_stop,
                    to_stop=to_stop,
                    total_fare=segment_fare,
                    status="Confirmed",
                    payment_id=payment_id,
                    payment_status="Paid",
                    payment_amount=segment_fare,
                    booking_date=timezone.now()
                )
                
                # Create the seat segment
                SeatSegment.objects.create(
                    booking=booking,
                    schedule=schedule,
                    seat_number=seat_number,
                    from_stop=from_stop,
                    to_stop=to_stop,
                    segment_fare=segment_fare,
                    is_active=True
                )

            messages.success(
                request, 
                f"Seat {seat_number} booked successfully from {from_stop.stop_name} to {to_stop.stop_name}!"
            )
            return redirect("traveller_bookings_page")

        except Exception as e:
            logger.error(f"Payment verification failed: {str(e)}")
            messages.error(request, f"Payment verification failed: {str(e)}")
            return redirect("book_bus", schedule_id=schedule.id)

    # Get booked segments for display
    booked_segments_list = []
    for segment in all_segments:
        booked_segments_list.append({
            'seat': segment.seat_number,
            'from': segment.from_stop.order,
            'to': segment.to_stop.order,
            'from_name': segment.from_stop.stop_name,
            'to_name': segment.to_stop.stop_name,
        })

    razorpay_key = settings.RAZORPAY_KEY_ID
    if not razorpay_key:
        logger.warning("RAZORPAY_KEY_ID is not set in settings!")
        messages.warning(request, "Payment system is not properly configured.")

    return render(request, "traveller/book_bus.html", {
        "bus": bus,
        "schedule": schedule,
        "stops": stops,
        "available_seats": available_seats,
        "seat_range": seat_range,
        "photos": photos,
        "price_per_stop": PRICE_PER_STOP,
        "razorpay_key": razorpay_key,
        "seat_availability_map": seat_availability_map,
        "total_stops": total_stops,
        "booked_segments_list": booked_segments_list,
    })


@login_required
def check_seat_availability(request):
    """Enhanced availability check for segments"""
    schedule_id = request.GET.get("schedule_id")
    seat_number = int(request.GET.get("seat_number"))
    from_order = int(request.GET.get("from_order"))
    to_order = int(request.GET.get("to_order"))

    is_available = is_segment_available(schedule_id, seat_number, from_order, to_order)
    
    # Also get available segments for this seat
    schedule = BusSchedule.objects.get(id=schedule_id)
    total_stops = schedule.route.stops.count()
    available_segments = get_available_segments(schedule_id, seat_number, total_stops)
    
    return JsonResponse({
        "available": is_available,
        "available_segments": available_segments,
        "message": "Segment available" if is_available else "This segment is already booked"
    })
@csrf_exempt
@login_required
def create_razorpay_order(request):
    if request.method != "POST":
        return JsonResponse({'error': 'Only POST allowed'}, status=405)

    try:
        data = json.loads(request.body)
        amount = int(data.get('amount'))

        if amount <= 0:
            return JsonResponse({'error': 'Invalid amount'}, status=400)

        client = razorpay.Client(auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET
        ))

        order = client.order.create({
            "amount": amount,
            "currency": "INR",
            "payment_capture": 1
        })

        return JsonResponse({
            "id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"]
        })

    except Exception as e:
        logger.error(str(e))
        return JsonResponse({'error': 'Server error'}, status=500)



# ============================================================
# BUS TRACKING
# ============================================================

@login_required
def track_bus(request, bus_id):
    """Track a specific bus"""
    bus = get_object_or_404(Bus, id=bus_id, approved=True)
    schedule = BusSchedule.objects.filter(bus=bus).order_by('-departure_time').first()
    photos = bus.photos.all()

    if not schedule:
        return render(request, 'traveller/track_bus.html', {
            'bus': bus,
            'error': 'No active schedule found.',
            'photos': photos
        })

    now = timezone.localtime()

    # Determine bus status
    if schedule.departure_time > now:
        status = "Yet to Depart"
    elif schedule.arrival_time < now:
        status = "Arrived"
    else:
        status = "On the Way"

    # Get route stops - ORDER BY 'order' field, NOT by arrival_time
    stops = list(schedule.route.stops.all().order_by('order'))
    
    # ========== FARE CALCULATION ==========
    # Same constants as in booking page
    PRICE_PER_STOP = Decimal("5.00")
    
    # Calculate total fare from first stop to last stop
    if stops and len(stops) >= 2:
        first_stop = stops[0]
        last_stop = stops[-1]
        stops_travelled = last_stop.order - first_stop.order
        total_fare = Decimal(schedule.fare) + (stops_travelled * PRICE_PER_STOP)
        stops_travelled_count = stops_travelled
    else:
        total_fare = Decimal(schedule.fare)
        stops_travelled_count = 0
    
    # ========== CURRENT/NEXT STOP LOGIC ==========
    current_stop = None
    next_stop = None
    current_time = now.time()

    # Find current and next stop based on order and time
    for i, stop in enumerate(stops):
        # If this stop's arrival time is in the future
        if stop.arrival_time > current_time:
            next_stop = stop
            # The previous stop is the current stop (if exists)
            if i > 0:
                current_stop = stops[i-1]
            break
    
    # If we've passed all stops, the last stop is current
    if next_stop is None and stops:
        current_stop = stops[-1]

    return render(request, 'traveller/track_bus.html', {
        'bus': bus,
        'schedule': schedule,
        'status': status,
        'current_stop': current_stop,
        'next_stop': next_stop,
        'stops': stops,
        'photos': photos,
        # Fare calculation context
        'total_fare': total_fare,
        'base_fare': schedule.fare,
        'price_per_stop': PRICE_PER_STOP,
        'stops_count': len(stops),
        'stops_travelled': stops_travelled_count,
    })

@login_required
def track_bus_list(request):
    """List all available buses for tracking"""
    buses = Bus.objects.filter(approved=True)
    return render(request, "traveller/track_bus_list.html", {
        "buses": buses
    })


# ============================================================
# CONCESSION APPLICATIONS
# ============================================================

@login_required
def apply_concession(request):
    """Apply for travel concession"""
    existing = ConcessionApplication.objects.filter(traveller=request.user).order_by('-applied_on').first()

    if existing and existing.status in ['Pending', 'Approved']:
        messages.warning(request, "You already have an active or pending concession application.")
        return redirect('traveller_dashboard')

    if request.method == "POST":
        college_name = request.POST.get('college_name')
        starting_location = request.POST.get('starting_location')
        ending_location = request.POST.get('ending_location')
        document = request.FILES.get('document')
        photo = request.FILES.get('photo')

        if college_name and starting_location and ending_location and document and photo:
            if existing and existing.status in ['Cancelled', 'Expired', 'Rejected']:
                existing.status = 'Archived'
                existing.save()

            ConcessionApplication.objects.create(
                traveller=request.user,
                college_name=college_name,
                starting_location=starting_location,
                ending_location=ending_location,
                document=document,
                photo=photo
            )

            messages.success(request, "Your concession application has been submitted successfully!")
            return redirect('traveller_dashboard')
        else:
            messages.error(request, "Please fill out all fields and upload both ID proof and photo.")

    return render(request, 'traveller/apply_concession.html')


@login_required
def view_concession_card(request, concession_id):
    """View approved concession card"""
    concession = get_object_or_404(ConcessionApplication, id=concession_id, traveller=request.user)

    if concession.status != 'Approved':
        return render(request, 'traveller/no_concession.html')

    concession_detail = ConcessionDetail.objects.filter(application=concession).first()

    return render(request, 'traveller/concession_card.html', {
        'concession': concession,
        'concession_detail': concession_detail
    })


@login_required
def concession_status(request):
    """Check concession application status"""
    concession = ConcessionApplication.objects.filter(traveller=request.user).order_by('-applied_on').first()
    return render(request, 'traveller/concession_status.html', {'concession': concession})


# ============================================================
# BUS SEARCH & AVAILABILITY
# ============================================================

@login_required
def search_buses(request):
    """Search buses by stop name"""
    query = request.GET.get("stop", "")
    results = []

    if query:
        stops = RouteStop.objects.filter(stop_name__icontains=query)
        if stops.exists():
            results = BusSchedule.objects.filter(
                route__in=[s.route for s in stops],
                bus__approved=True,
                active=True
            ).select_related("bus", "route")

    return render(request, "traveller/search_buses.html", {
        "query": query,
        "results": results,
    })


from django.db.models import Q
from datetime import time

@login_required
def available_buses(request):
    buses = Bus.objects.filter(approved=True)

    source = request.GET.get('source')
    destination = request.GET.get('destination')
    time_input = request.GET.get('time')

    if source and destination and time_input:
        time_obj = time.fromisoformat(time_input)

        valid_schedules = []

        schedules = BusSchedule.objects.filter(active=True).select_related('route', 'bus')

        for schedule in schedules:
            stops = schedule.route.stops.all().order_by('order')

            source_stop = None
            dest_stop = None

            for stop in stops:
                if stop.stop_name.lower() == source.lower():
                    source_stop = stop
                if stop.stop_name.lower() == destination.lower():
                    dest_stop = stop

            # ✅ Check conditions
            if source_stop and dest_stop:
                if source_stop.order < dest_stop.order:
                    if source_stop.arrival_time >= time_obj:
                        valid_schedules.append(schedule)

        buses = Bus.objects.filter(schedules__in=valid_schedules).distinct()

    return render(request, 'traveller/available_buses.html', {
        'buses': buses
    })
# ============================================================
# BOOKINGS & TICKETS
# ============================================================

@login_required
def traveller_bookings_page(request):
    """View all bookings for the logged-in traveller"""
    bookings = Booking.objects.filter(traveller=request.user).order_by('-booking_date')
    
    # Calculate counts for stats cards
    confirmed_count = bookings.filter(status="Confirmed").count()
    pending_count = bookings.filter(status="Pending").count()
    cancelled_count = bookings.filter(status="Cancelled").count()
    
    context = {
        'bookings': bookings,
        'confirmed_count': confirmed_count,
        'pending_count': pending_count,
        'cancelled_count': cancelled_count,
    }
    
    return render(request, 'traveller/traveller_bookings.html', context)


@login_required
def view_ticket(request, booking_id):
    """View ticket HTML page"""
    booking = get_object_or_404(
        Booking,
        id=booking_id,
        traveller=request.user
    )
    return render(request, "traveller/ticket.html", {"booking": booking})


@login_required
def download_ticket(request, booking_id):
    """Download ticket as PDF using ReportLab"""
    booking = get_object_or_404(
        Booking,
        id=booking_id,
        traveller=request.user
    )

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="BusEase_Ticket_{booking.id}.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    
    # Add custom styles
    styles.add(ParagraphStyle(
        name='CenterTitle',
        parent=styles['Title'],
        alignment=1,
        spaceAfter=20,
        textColor=colors.HexColor('#003366')
    ))
    
    styles.add(ParagraphStyle(
        name='GovernmentHeader',
        parent=styles['Normal'],
        alignment=1,
        textColor=colors.HexColor('#FFD700'),
        backColor=colors.HexColor('#003366'),
        spaceAfter=10,
        spaceBefore=10,
        fontSize=12
    ))

    elements = []

    # Government Header
    elements.append(Paragraph(
        "<b>GOVERNMENT OF INDIA</b>", 
        styles['CenterTitle']
    ))
    elements.append(Paragraph(
        "Ministry of Road Transport & Highways",
        styles['GovernmentHeader']
    ))
    elements.append(Spacer(1, 20))

    # Title
    elements.append(Paragraph(
        "<b>Bus Travel Ticket</b>", 
        styles['Title']
    ))
    elements.append(Spacer(1, 20))

    # Ticket Details Table
    data = [
        ["Booking ID:", str(booking.id)],
        ["Passenger:", booking.traveller.get_full_name() or booking.traveller.username],
        ["Bus:", f"{booking.bus.bus_name} ({booking.bus.bus_number})"],
        ["From:", booking.from_stop.stop_name if booking.from_stop else "—"],
        ["To:", booking.to_stop.stop_name if booking.to_stop else "—"],
        ["Seat Number:", str(booking.seat_number)],
        ["Departure:", booking.schedule.departure_time.strftime("%d %b %Y, %I:%M %p") if booking.schedule else "—"],
        ["Total Fare:", f"₹ {booking.total_fare}"],
        ["Status:", booking.status],
        ["Booked On:", booking.booking_date.strftime("%d %b %Y, %I:%M %p")],
    ]

    table = Table(data, colWidths=[120, 380])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor('#003366')),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor('#FFD700')),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BACKGROUND", (1, 0), (1, -1), colors.whitesmoke),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("PADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 30))

    # Footer Note
    elements.append(Paragraph(
        "✓ Valid with government ID proof",
        styles['Normal']
    ))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph(
        "<b>Computer generated authorized ticket</b>",
        styles['Normal']
    ))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph(
        "Thank you for choosing Government Transport Services",
        styles['Normal']
    ))
    elements.append(Spacer(1, 15))
    elements.append(Paragraph(
        "<font color='#003366'><b>BusEase - Government Transport Portal</b></font>",
        styles['Normal']
    ))

    doc.build(elements)
    return response


@login_required
def download_ticket_pdf(request, booking_id):
    """Download ticket as PDF using xhtml2pdf (alternative method)"""
    booking = get_object_or_404(
        Booking,
        id=booking_id,
        traveller=request.user
    )

    template = get_template("traveller/ticket_pdf.html")
    html = template.render({"booking": booking})

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="BusEase_Ticket_{booking.id}.pdf"'
    )

    pisa_status = pisa.CreatePDF(html, dest=response)

    if pisa_status.err:
        return HttpResponse("Error generating PDF", status=500)

    return response


# ============================================================
# BUS REVIEWS
# ============================================================

@login_required
def add_bus_review(request, bus_id):
    """Add a review for a bus"""
    bus = get_object_or_404(Bus, id=bus_id, approved=True)
    
    if request.method == "POST":
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        
        # Check if user already reviewed this bus
        existing_review = BusReview.objects.filter(
            bus=bus, 
            traveller=request.user
        ).first()
        
        if existing_review:
            existing_review.rating = rating
            existing_review.comment = comment
            existing_review.save()
            messages.success(request, "Your review has been updated!")
        else:
            BusReview.objects.create(
                bus=bus,
                traveller=request.user,
                rating=rating,
                comment=comment
            )
            messages.success(request, "Thank you for your review!")
        
        return redirect('view_schedules', bus_id=bus.id)
    
    return render(request, 'traveller/add_bus_review.html', {'bus': bus})


from django.http import JsonResponse

@login_required
def check_seat_availability(request):
    schedule_id = request.GET.get("schedule_id")
    seat_number = request.GET.get("seat_number")
    from_order = int(request.GET.get("from_order"))
    to_order = int(request.GET.get("to_order"))

    bookings = Booking.objects.filter(
        schedule_id=schedule_id,
        seat_number=seat_number
    )

    for b in bookings:
        if not (to_order <= b.from_stop.order or from_order >= b.to_stop.order):
            return JsonResponse({"available": False})

    return JsonResponse({"available": True})


@login_required
def get_available_seats_for_boarding(request):
    """Get available seats for a specific boarding point"""
    schedule_id = request.GET.get('schedule_id')
    boarding_stop_id = request.GET.get('boarding_stop_id')
    
    if not schedule_id or not boarding_stop_id:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        schedule = BusSchedule.objects.get(id=schedule_id)
        boarding_stop = RouteStop.objects.get(id=boarding_stop_id)
        total_stops = schedule.route.stops.count()
        
        available_seats = []
        seat_details = {}
        
        for seat_num in range(1, schedule.bus.total_seats + 1):
            # Get available segments from this boarding point
            available_segments = get_available_segments_from_boarding(
                schedule_id, seat_num, boarding_stop.order, total_stops
            )
            
            if available_segments:
                available_seats.append(seat_num)
                seat_details[seat_num] = {
                    'available_segments': available_segments,
                    'max_destination': max([seg[1] for seg in available_segments]),
                    'min_destination': min([seg[1] for seg in available_segments])
                }
        
        return JsonResponse({
            'available_seats': available_seats,
            'seat_details': seat_details,
            'boarding_stop': {
                'id': boarding_stop.id,
                'name': boarding_stop.stop_name,
                'order': boarding_stop.order
            }
        })
    except Exception as e:
        logger.error(f"Error getting available seats: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_available_destinations_for_seat(request):
    """Get available destinations for a specific seat after selecting boarding point"""
    schedule_id = request.GET.get('schedule_id')
    seat_number = request.GET.get('seat_number')
    boarding_order = request.GET.get('boarding_order')
    
    if not all([schedule_id, seat_number, boarding_order]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        schedule = BusSchedule.objects.get(id=schedule_id)
        boarding_order = int(boarding_order)
        seat_number = int(seat_number)
        total_stops = schedule.route.stops.count()
        
        # Get available segments from this boarding point
        available_segments = get_available_segments_from_boarding(
            schedule_id, seat_number, boarding_order, total_stops
        )
        
        # Get all stops
        stops = list(schedule.route.stops.all().order_by('order'))
        
        # Get occupied segments for display
        occupied_segments = SeatSegment.objects.filter(
            schedule_id=schedule_id,
            seat_number=seat_number,
            is_active=True
        ).select_related('from_stop', 'to_stop')
        
        occupied_info = []
        for segment in occupied_segments:
            occupied_info.append({
                'from': segment.from_stop.stop_name,
                'to': segment.to_stop.stop_name,
                'from_order': segment.from_stop.order,
                'to_order': segment.to_stop.order
            })
        
        # Build available destinations
        available_destinations = []
        for from_order, to_order in available_segments:
            # Find the destination stop details
            dest_stop = next((s for s in stops if s.order == to_order), None)
            if dest_stop:
                available_destinations.append({
                    'id': dest_stop.id,
                    'name': dest_stop.stop_name,
                    'order': dest_stop.order,
                    'arrival_time': dest_stop.arrival_time.strftime("%I:%M %p")
                })
        
        return JsonResponse({
            'available_destinations': available_destinations,
            'occupied_segments': occupied_info,
            'seat_number': seat_number,
            'has_available_segments': len(available_destinations) > 0,
            'message': generate_occupancy_message(occupied_info, boarding_order)
        })
    except Exception as e:
        logger.error(f"Error getting destinations: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def get_available_segments_from_boarding(schedule_id, seat_number, boarding_order, total_stops):
    """Helper function to get available segments from a specific boarding point"""
    # Get all booked segments for this seat
    booked_segments = SeatSegment.objects.filter(
        schedule_id=schedule_id,
        seat_number=seat_number,
        is_active=True
    ).values_list('from_stop__order', 'to_stop__order')
    
    if not booked_segments:
        # No bookings, entire route available from boarding point
        return [(boarding_order, stop) for stop in range(boarding_order + 1, total_stops + 1)]
    
    # Sort booked segments
    booked_list = sorted([(f, t) for f, t in booked_segments])
    
    # Find available segments starting from boarding_order
    available = []
    current_pos = boarding_order
    
    for from_order, to_order in booked_list:
        if from_order >= current_pos:
            # Gap before this booked segment
            if current_pos < from_order:
                available.append((current_pos, from_order))
            current_pos = max(current_pos, to_order)
    
    # Remaining after last booking
    if current_pos < total_stops:
        available.append((current_pos, total_stops))
    
    # Filter to only include segments starting exactly at boarding_order
    # (Strict sequential behavior)
    filtered_available = [(f, t) for f, t in available if f == boarding_order]
    
    return filtered_available


def generate_occupancy_message(occupied_segments, boarding_order):
    """Generate user-friendly message about occupied segments"""
    if not occupied_segments:
        return None
    
    message = "⚠️ This seat is already booked for:\n"
    for seg in occupied_segments:
        message += f"• {seg['from']} → {seg['to']}\n"
    
    # Check if boarding point is within occupied segment
    for seg in occupied_segments:
        if seg['from_order'] <= boarding_order < seg['to_order']:
            message += f"\n❌ You cannot board at this stop as the seat is occupied until {seg['to']}."
            message += f"\n✓ Available from {seg['to']} onwards."
            return message
    
    message += f"\n✓ You can book from the available stops shown above."
    return message

@login_required
def get_seat_status(request):
    """API endpoint to get status of a specific seat"""
    schedule_id = request.GET.get('schedule_id')
    seat_number = request.GET.get('seat_number')
    
    if not schedule_id or not seat_number:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        from bus_owner.models import BusSchedule, RouteStop
        from .models import SeatSegment
        
        schedule = BusSchedule.objects.get(id=schedule_id)
        total_stops = schedule.route.stops.count()
        seat_number = int(seat_number)
        
        # Get available segments from utils function
        from .utils import get_available_segments
        
        available_segments = get_available_segments(schedule_id, seat_number, total_stops)
        
        # Get booked segments for this seat
        booked_segments = SeatSegment.objects.filter(
            schedule_id=schedule_id,
            seat_number=seat_number,
            is_active=True
        ).select_related('from_stop', 'to_stop')
        
        # Format available segments for display
        stops = list(schedule.route.stops.all().order_by('order'))
        available_segments_text = []
        for from_order, to_order in available_segments:
            from_stop = next((s for s in stops if s.order == from_order), None)
            to_stop = next((s for s in stops if s.order == to_order), None)
            if from_stop and to_stop:
                available_segments_text.append(f"{from_stop.stop_name} → {to_stop.stop_name}")
        
        return JsonResponse({
            'seat_number': seat_number,
            'is_fully_booked': len(available_segments) == 0,
            'has_available_segments': len(available_segments) > 0,
            'available_segments': available_segments,
            'available_segments_text': ', '.join(available_segments_text),
            'booked_segments_count': booked_segments.count()
        })
    except Exception as e:
        logger.error(f"Error getting seat status: {str(e)}")
        return JsonResponse({'error': str(e), 'is_fully_booked': False, 'has_available_segments': True}, status=200)


@login_required
def get_available_seats_for_boarding(request):
    """Get available seats for a specific boarding point"""
    schedule_id = request.GET.get('schedule_id')
    boarding_stop_id = request.GET.get('boarding_stop_id')
    
    if not schedule_id or not boarding_stop_id:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        from bus_owner.models import BusSchedule, RouteStop
        from .models import SeatSegment
        from .utils import get_available_segments
        
        schedule = BusSchedule.objects.get(id=schedule_id)
        boarding_stop = RouteStop.objects.get(id=boarding_stop_id)
        total_stops = schedule.route.stops.count()
        
        available_seats = []
        seat_details = {}
        
        for seat_num in range(1, schedule.bus.total_seats + 1):
            # Get available segments from this boarding point
            available_segments = get_available_segments(schedule_id, seat_num, total_stops)
            
            # Filter segments that start exactly at boarding point
            valid_segments = [(f, t) for f, t in available_segments if f == boarding_stop.order]
            
            if valid_segments:
                available_seats.append(seat_num)
                seat_details[seat_num] = {
                    'available_segments': valid_segments,
                    'max_destination': max([seg[1] for seg in valid_segments]),
                    'min_destination': min([seg[1] for seg in valid_segments])
                }
        
        return JsonResponse({
            'available_seats': available_seats,
            'seat_details': seat_details,
            'boarding_stop': {
                'id': boarding_stop.id,
                'name': boarding_stop.stop_name,
                'order': boarding_stop.order
            }
        })
    except Exception as e:
        logger.error(f"Error getting available seats: {str(e)}")
        return JsonResponse({'error': str(e), 'available_seats': []}, status=200)


@login_required
def get_available_destinations_for_seat(request):
    """Get available destinations for a specific seat after selecting boarding point"""
    schedule_id = request.GET.get('schedule_id')
    seat_number = request.GET.get('seat_number')
    boarding_order = request.GET.get('boarding_order')
    
    if not all([schedule_id, seat_number, boarding_order]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        from bus_owner.models import BusSchedule, RouteStop
        from .models import SeatSegment
        from .utils import get_available_segments
        
        schedule = BusSchedule.objects.get(id=schedule_id)
        boarding_order = int(boarding_order)
        seat_number = int(seat_number)
        total_stops = schedule.route.stops.count()
        
        # Get available segments from this boarding point
        available_segments = get_available_segments(schedule_id, seat_number, total_stops)
        
        # Filter segments that start exactly at boarding point
        valid_segments = [(f, t) for f, t in available_segments if f == boarding_order]
        
        # Get all stops
        stops = list(schedule.route.stops.all().order_by('order'))
        
        # Get occupied segments for display
        occupied_segments = SeatSegment.objects.filter(
            schedule_id=schedule_id,
            seat_number=seat_number,
            is_active=True
        ).select_related('from_stop', 'to_stop')
        
        occupied_info = []
        for segment in occupied_segments:
            occupied_info.append({
                'from': segment.from_stop.stop_name,
                'to': segment.to_stop.stop_name,
                'from_order': segment.from_stop.order,
                'to_order': segment.to_stop.order
            })
        
        # Build available destinations
        available_destinations = []
        for from_order, to_order in valid_segments:
            # Find the destination stop details
            dest_stop = next((s for s in stops if s.order == to_order), None)
            if dest_stop:
                available_destinations.append({
                    'id': dest_stop.id,
                    'name': dest_stop.stop_name,
                    'order': dest_stop.order,
                    'arrival_time': dest_stop.arrival_time.strftime("%I:%M %p")
                })
        
        # Generate message
        message = None
        if occupied_info:
            message = "⚠️ This seat is already booked for:\n"
            for seg in occupied_info:
                message += f"• {seg['from']} → {seg['to']}\n"
            
            # Check if boarding point is within occupied segment
            for seg in occupied_info:
                if seg['from_order'] <= boarding_order < seg['to_order']:
                    message += f"\n❌ You cannot board at this stop as the seat is occupied until {seg['to']}."
                    message += f"\n✓ Available from {seg['to']} onwards."
                else:
                    message += f"\n✓ You can book from the available stops shown above."
        
        return JsonResponse({
            'available_destinations': available_destinations,
            'occupied_segments': occupied_info,
            'seat_number': seat_number,
            'has_available_segments': len(available_destinations) > 0,
            'message': message
        })
    except Exception as e:
        logger.error(f"Error getting destinations: {str(e)}")
        return JsonResponse({'error': str(e), 'has_available_segments': False}, status=200)


@login_required
def get_seat_segments(request):
    """Get available segments for a specific seat"""
    schedule_id = request.GET.get('schedule_id')
    seat_number = request.GET.get('seat_number')
    
    if not schedule_id or not seat_number:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        from bus_owner.models import BusSchedule, RouteStop
        from .utils import get_available_segments
        
        schedule = BusSchedule.objects.get(id=schedule_id)
        total_stops = schedule.route.stops.count()
        seat_number = int(seat_number)
        
        available_segments = get_available_segments(schedule_id, seat_number, total_stops)
        
        # Format available segments for display
        stops = list(schedule.route.stops.all().order_by('order'))
        formatted_segments = []
        for from_order, to_order in available_segments:
            from_stop = next((s for s in stops if s.order == from_order), None)
            to_stop = next((s for s in stops if s.order == to_order), None)
            if from_stop and to_stop:
                formatted_segments.append({
                    'from': from_stop.stop_name,
                    'to': to_stop.stop_name,
                    'from_order': from_order,
                    'to_order': to_order
                })
        
        return JsonResponse({
            'seat_number': seat_number,
            'available_segments': available_segments,
            'formatted_segments': formatted_segments,
            'has_available_segments': len(available_segments) > 0
        })
    except Exception as e:
        logger.error(f"Error getting seat segments: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)