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

@login_required
def book_bus(request, schedule_id):
    """Book a bus seat with Razorpay payment"""
    schedule = get_object_or_404(
        BusSchedule.objects.select_related("bus", "route"),
        id=schedule_id
    )

    bus = schedule.bus
    route = schedule.route
    photos = bus.photos.all()

    # Stops
    stops = list(route.stops.all().order_by("order"))

    booked_seats = Booking.objects.filter(schedule=schedule).count()
    available_seats = bus.total_seats - booked_seats

    PRICE_PER_STOP = Decimal("5.00")  # FIXED RATE

    if request.method == "POST":
        seat_number = request.POST.get("seat_number")
        from_stop_id = request.POST.get("from_stop")
        to_stop_id = request.POST.get("to_stop")
        payment_id = request.POST.get("razorpay_payment_id")
        
        if not seat_number or not from_stop_id or not to_stop_id:
            messages.error(request, "All fields are required.")
            return redirect("book_bus", schedule_id=schedule.id)

        from_stop = get_object_or_404(RouteStop, id=from_stop_id)
        to_stop = get_object_or_404(RouteStop, id=to_stop_id)

        if from_stop.order >= to_stop.order:
            messages.error(request, "Destination must be after boarding stop.")
            return redirect("book_bus", schedule_id=schedule.id)

        if Booking.objects.filter(
            schedule=schedule,
            seat_number=seat_number
        ).exists():
            messages.error(request, "Seat already booked.")
            return redirect("book_bus", schedule_id=schedule.id)

        # Calculate total fare
        stops_travelled = to_stop.order - from_stop.order
        base_fare = Decimal(schedule.fare)
        total_fare = base_fare + (stops_travelled * PRICE_PER_STOP)
        
        # Calculate journey duration between selected stops
        # Assuming stops have arrival times, we can calculate the difference
        journey_duration = None
        try:
            # Convert time to datetime for calculation
            from datetime import datetime, timedelta
            from_stop_time = datetime.combine(datetime.today(), from_stop.arrival_time)
            to_stop_time = datetime.combine(datetime.today(), to_stop.arrival_time)
            
            # If to_stop_time is less than from_stop_time, it means it's next day
            if to_stop_time < from_stop_time:
                to_stop_time += timedelta(days=1)
            
            journey_duration = to_stop_time - from_stop_time
        except Exception as e:
            # Fallback if time calculation fails
            journey_duration = timedelta(hours=2, minutes=30)  # Default 2h30m
            print(f"Error calculating duration: {e}")

        # Verify payment if payment_id exists
        if payment_id:
            try:
                client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
                client.payment.fetch(payment_id)
                
                # Create booking after successful payment
                booking = Booking.objects.create(
                    traveller=request.user,
                    bus=bus,
                    schedule=schedule,
                    seat_number=seat_number,
                    from_stop=from_stop,
                    to_stop=to_stop,
                    total_fare=total_fare,
                    status="Confirmed",
                    payment_id=payment_id,
                    payment_status="Paid",
                    journey_duration=journey_duration  # Store the calculated duration
                )
                
                messages.success(
                    request,
                    f"Booking successful! Ticket Price: ₹{total_fare}"
                )
                return redirect("traveller_bookings_page")
                
            except Exception as e:
                messages.error(request, f"Payment verification failed: {str(e)}")
                return redirect("book_bus", schedule_id=schedule.id)
        else:
            messages.error(request, "Payment failed. Please try again.")
            return redirect("book_bus", schedule_id=schedule.id)

    return render(request, "traveller/book_bus.html", {
        "bus": bus,
        "schedule": schedule,
        "stops": stops,
        "available_seats": available_seats,
        "photos": photos,
        "price_per_stop": PRICE_PER_STOP,
        "razorpay_key": settings.RAZORPAY_KEY_ID,
        "currency": "INR",
    })


# ============================================================
# RAZORPAY PAYMENT INTEGRATION
# ============================================================

@login_required
def create_razorpay_order(request):
    """Create a Razorpay order for payment"""
    if request.method != "POST":
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        amount = int(data.get('amount', 0))
        
        if amount <= 0:
            return JsonResponse({'error': 'Invalid amount. Amount must be greater than 0.'}, status=400)
        
        if amount > 5000000:  # ₹50,000 max
            return JsonResponse({'error': 'Amount exceeds maximum limit'}, status=400)
        
        client = razorpay.Client(auth=(
            settings.RAZORPAY_KEY_ID, 
            settings.RAZORPAY_KEY_SECRET
        ))
        
        order_data = {
            'amount': amount,
            'currency': 'INR',
            'payment_capture': 1,
            'notes': {
                'user_id': request.user.id,
                'username': request.user.username
            }
        }
        
        order = client.order.create(order_data)
        logger.info(f"Order created: {order['id']} for user {request.user.username}")
        
        return JsonResponse({
            'id': order['id'],
            'amount': order['amount'],
            'currency': order['currency'],
            'status': 'success'
        })
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in request body")
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)
    except razorpay.errors.BadRequestError as e:
        logger.error(f"Razorpay error: {str(e)}")
        return JsonResponse({'error': f'Razorpay error: {str(e)}'}, status=400)
    except razorpay.errors.ServerError as e:
        logger.error(f"Razorpay server error: {str(e)}")
        return JsonResponse({'error': 'Payment service temporarily unavailable'}, status=503)
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return JsonResponse({'error': 'An unexpected error occurred'}, status=500)


@csrf_exempt
def verify_payment(request):
    """Verify Razorpay payment signature"""
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            payment_id = data.get('razorpay_payment_id')
            order_id = data.get('razorpay_order_id')
            signature = data.get('razorpay_signature')
            
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            
            params_dict = {
                'razorpay_payment_id': payment_id,
                'razorpay_order_id': order_id,
                'razorpay_signature': signature
            }
            
            client.utility.verify_payment_signature(params_dict)
            return JsonResponse({"status": "success"})
        except Exception as e:
            logger.error(f"Payment verification failed: {str(e)}")
            return JsonResponse({"status": "failed", "error": str(e)}, status=400)
    
    return JsonResponse({'error': 'Invalid request method'}, status=405)


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


@login_required
def available_buses(request):
    """List all approved buses"""
    buses = Bus.objects.filter(approved=True)
    return render(request, 'traveller/available_buses.html', {'buses': buses})


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