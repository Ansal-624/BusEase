from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST

# Import models from bus_owner app (not from conductor.models)
from bus_owner.models import Conductor, ConductorDuty, Bus, BusSchedule
from traveller.models import Booking
import json
from decimal import Decimal
from django.db import transaction  # Add this import


@login_required
def conductor_dashboard(request):
    try:
        conductor = Conductor.objects.get(user=request.user)
    except Conductor.DoesNotExist:
        messages.error(request, "Conductor profile not found.")
        return redirect('home')
    
    current_duty = ConductorDuty.objects.filter(
        conductor=conductor,
        is_active=True
    ).first()
    
    assigned_bus = current_duty.bus if current_duty else None
    has_assignment = assigned_bus is not None
    
    today = timezone.now().date()

    today_schedules = []
    current_schedule = None

    if assigned_bus:
       today_schedules = BusSchedule.objects.filter(
        bus=assigned_bus,
        departure_time__date=today,
        active=True
    ).select_related('route').order_by('departure_time')

    # ✅ FIX STARTS HERE
    if today_schedules.exists():
        current_schedule = today_schedules.first()
    else:
        current_schedule = BusSchedule.objects.filter(
            bus=assigned_bus,
            active=True
        ).select_related('route').first()
    # ✅ FIX ENDS HERE

    recent_bookings = []
    if assigned_bus:
        recent_bookings = Booking.objects.filter(
            bus=assigned_bus
        ).select_related('traveller', 'schedule').order_by('-booking_date')[:10]
    
    context = {
        'conductor': conductor,
        'assigned_bus': assigned_bus,
        'has_assignment': has_assignment,
        'today_schedules': today_schedules,
        'recent_bookings': recent_bookings,
        'today': today,
        'schedule': current_schedule,  # ✅ correct now
    }
    
    return render(request, 'conductor/dashboard.html', context)

@login_required
def conductor_seat_management(request, bus_id):
    """Conductor seat management page for a specific bus"""
    try:
        from traveller.models import SeatSegment
        
        conductor = Conductor.objects.get(user=request.user)
    except Conductor.DoesNotExist:
        messages.error(request, "Conductor profile not found.")
        return redirect('home')
    
    # Verify conductor is assigned to this bus
    current_duty = ConductorDuty.objects.filter(
        conductor=conductor,
        bus_id=bus_id,
        is_active=True
    ).first()
    
    if not current_duty:
        messages.error(request, "You are not authorized to manage this bus.")
        return redirect('conductor_dashboard')
    
    bus = get_object_or_404(Bus, id=bus_id)
    
    # Get schedule
    schedule = BusSchedule.objects.filter(bus=bus, active=True).first()
    
    # Get all stops for the route
    stops = []
    price_per_stop = Decimal("5.00")
    base_fare = Decimal("0")
    
    if schedule and schedule.route:
        stops = schedule.route.stops.all().order_by('order')
        
        # Calculate base fare and price per stop
        if stops.count() >= 2:
            first_stop = stops.first()
            last_stop = stops.last()
            stops_travelled_total = last_stop.order - first_stop.order
            if stops_travelled_total > 0:
                base_fare = Decimal(str(schedule.fare))
    
    # Get all bookings for this bus
    bookings = Booking.objects.filter(
        bus=bus,
        status='Confirmed'
    ).values_list('seat_number', flat=True)
    
    booked_seats = list(bookings)
    
    # Get seat segment information for tooltips
    seat_segments = SeatSegment.objects.filter(
        schedule=schedule,
        is_active=True
    ).select_related('from_stop', 'to_stop')
    
    seat_booking_map = {}
    for segment in seat_segments:
        seat = segment.seat_number
        if seat not in seat_booking_map:
            seat_booking_map[seat] = []
        seat_booking_map[seat].append({
            'from_name': segment.from_stop.stop_name,
            'to_name': segment.to_stop.stop_name,
            'from_order': segment.from_stop.order,
            'to_order': segment.to_stop.order
        })
    
    # Create seat range
    seat_range = range(1, bus.total_seats + 1)
    
    context = {
        'bus': bus,
        'seat_range': seat_range,
        'booked_seats': booked_seats,
        'seat_booking_map': seat_booking_map,  # Pass for tooltips
        'total_seats': bus.total_seats,
        'schedule': schedule,
        'stops': stops,
        'price_per_stop': price_per_stop,
        'base_fare': base_fare,
    }
    
    return render(request, 'conductor/seat_management.html', context)

@login_required
def conductor_update_seat_status(request):
    """Update seat status with boarding and dropping points"""
    if request.method == 'POST':
        try:
            from decimal import Decimal
            from traveller.models import SeatSegment  # Add this import
            
            conductor = Conductor.objects.get(user=request.user)
            seat_number = request.POST.get('seat_number')
            passenger_name = request.POST.get('passenger_name')
            passenger_phone = request.POST.get('passenger_phone')
            fare_collected = request.POST.get('fare_collected')
            payment_status = request.POST.get('payment_status')  # 'paid' or 'unpaid'
            boarding_stop_id = request.POST.get('boarding_stop')
            dropping_stop_id = request.POST.get('dropping_stop')
            notes = request.POST.get('notes', '')
            
            # Get the bus from conductor's assignment
            current_duty = ConductorDuty.objects.filter(
                conductor=conductor,
                is_active=True
            ).first()
            
            if not current_duty:
                messages.error(request, 'No bus assigned')
                return redirect('conductor_dashboard')
            
            bus = current_duty.bus
            
            # Get schedule for this bus
            schedule = BusSchedule.objects.filter(bus=bus, active=True).first()
            
            if not schedule:
                messages.error(request, 'No active schedule found for this bus.')
                return redirect('conductor_dashboard')
            
            # Get boarding and dropping stops
            boarding_stop = get_object_or_404(RouteStop, id=boarding_stop_id)
            dropping_stop = get_object_or_404(RouteStop, id=dropping_stop_id)
            
            # Validate stops order
            if boarding_stop.order >= dropping_stop.order:
                messages.error(request, 'Invalid stops selected. Dropping point must be after boarding point.')
                return redirect('conductor_seat_management', bus_id=bus.id)
            
            # Calculate fare if not provided
            if not fare_collected:
                PRICE_PER_STOP = Decimal("5.00")
                stops_travelled = dropping_stop.order - boarding_stop.order
                fare_collected = Decimal(schedule.fare) + (stops_travelled * PRICE_PER_STOP)
            else:
                fare_collected = Decimal(str(fare_collected))
            
            # Set payment status for booking
            payment_status_value = 'Paid' if payment_status == 'paid' else 'Pending'
            booking_status = 'Confirmed'
            
            # Store passenger details in notes
            passenger_info = f"Conductor Booking - Passenger: {passenger_name}, Phone: {passenger_phone}"
            if notes:
                passenger_info += f" | Notes: {notes}"
            
            # Check if booking already exists for this seat
            existing_booking = Booking.objects.filter(
                bus=bus,
                seat_number=seat_number,
                schedule=schedule
            ).first()
            
            with transaction.atomic():
                if existing_booking:
                    # Update existing booking
                    existing_booking.traveller = conductor.user
                    existing_booking.total_fare = fare_collected
                    existing_booking.status = booking_status
                    existing_booking.payment_status = payment_status_value
                    existing_booking.payment_amount = fare_collected if payment_status == 'paid' else 0
                    existing_booking.from_stop = boarding_stop
                    existing_booking.to_stop = dropping_stop
                    existing_booking.save()
                    booking = existing_booking
                    
                    # Update existing seat segment or create new one
                    existing_segment = SeatSegment.objects.filter(
                        booking=booking,
                        schedule=schedule,
                        seat_number=seat_number,
                        is_active=True
                    ).first()
                    
                    if existing_segment:
                        existing_segment.from_stop = boarding_stop
                        existing_segment.to_stop = dropping_stop
                        existing_segment.segment_fare = fare_collected
                        existing_segment.save()
                    else:
                        SeatSegment.objects.create(
                            booking=booking,
                            schedule=schedule,
                            seat_number=seat_number,
                            from_stop=boarding_stop,
                            to_stop=dropping_stop,
                            segment_fare=fare_collected,
                            is_active=True
                        )
                else:
                    # Create new booking
                    booking = Booking.objects.create(
                        bus=bus,
                        seat_number=seat_number,
                        schedule=schedule,
                        traveller=conductor.user,
                        total_fare=fare_collected,
                        status=booking_status,
                        payment_status=payment_status_value,
                        payment_amount=fare_collected if payment_status == 'paid' else 0,
                        booking_date=timezone.now(),
                        from_stop=boarding_stop,
                        to_stop=dropping_stop
                    )
                    
                    # ✅ CRITICAL: Create the seat segment
                    SeatSegment.objects.create(
                        booking=booking,
                        schedule=schedule,
                        seat_number=seat_number,
                        from_stop=boarding_stop,
                        to_stop=dropping_stop,
                        segment_fare=fare_collected,
                        is_active=True
                    )
            
            payment_text = "with payment" if payment_status == 'paid' else "without payment"
            messages.success(
                request, 
                f'✅ Seat {seat_number} booked for {passenger_name} from {boarding_stop.stop_name} to {dropping_stop.stop_name} {payment_text}'
            )
            
            return redirect('conductor_seat_management', bus_id=bus.id)
            
        except Conductor.DoesNotExist:
            messages.error(request, 'Conductor profile not found')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            import traceback
            traceback.print_exc()
    
    return redirect('conductor_dashboard')

@login_required
def conductor_current_duty(request):
    """Get current duty information for the conductor (API endpoint)"""
    try:
        conductor = Conductor.objects.get(user=request.user)
        current_duty = ConductorDuty.objects.filter(
            conductor=conductor,
            is_active=True
        ).first()
        
        if current_duty:
            data = {
                'has_duty': True,
                'bus_id': current_duty.bus.id,
                'bus_name': current_duty.bus.bus_name,
                'bus_number': current_duty.bus.bus_number,
                'assigned_at': current_duty.assigned_at.isoformat(),
            }
        else:
            data = {'has_duty': False}
        
        return JsonResponse(data)
        
    except Conductor.DoesNotExist:
        return JsonResponse({'error': 'Conductor not found'}, status=404)


@login_required
def conductor_schedules(request):
    """View all schedules for conductor's assigned bus"""
    try:
        conductor = Conductor.objects.get(user=request.user)
        current_duty = ConductorDuty.objects.filter(
            conductor=conductor,
            is_active=True
        ).first()
        
        if not current_duty:
            messages.error(request, "No bus assigned to you.")
            return redirect('conductor_dashboard')
        
        bus = current_duty.bus
        
        # Get all schedules for this bus
        schedules = BusSchedule.objects.filter(
            bus=bus,
            active=True
        ).select_related('route').order_by('departure_time')
        
        context = {
            'bus': bus,
            'schedules': schedules,
        }
        
        return render(request, 'conductor/schedules.html', context)
        
    except Conductor.DoesNotExist:
        messages.error(request, "Conductor profile not found.")
        return redirect('home')


@login_required
def conductor_bookings(request):
    """View all bookings for conductor's assigned bus"""
    try:
        conductor = Conductor.objects.get(user=request.user)
        current_duty = ConductorDuty.objects.filter(
            conductor=conductor,
            is_active=True
        ).first()
        
        if not current_duty:
            messages.error(request, "No bus assigned to you.")
            return redirect('conductor_dashboard')
        
        bus = current_duty.bus
        
        # Get all bookings for this bus
        bookings = Booking.objects.filter(
            bus=bus
        ).select_related('traveller', 'schedule').order_by('-booking_date')
        
        context = {
            'bus': bus,
            'bookings': bookings,
        }
        
        return render(request, 'conductor/bookings.html', context)
        
    except Conductor.DoesNotExist:
        messages.error(request, "Conductor profile not found.")
        return redirect('home')


@login_required
def conductor_cancel_booking(request):
    """Cancel a booked seat - UPDATE the booking status and deactivate seat segment"""
    if request.method == 'POST':
        try:
            from traveller.models import SeatSegment
            
            conductor = Conductor.objects.get(user=request.user)
            seat_number = request.POST.get('seat_number')
            cancel_reason = request.POST.get('cancel_reason', '')
            
            # Get the bus from conductor's assignment
            current_duty = ConductorDuty.objects.filter(
                conductor=conductor,
                is_active=True
            ).first()
            
            if not current_duty:
                messages.error(request, 'No bus assigned')
                return redirect('conductor_dashboard')
            
            bus = current_duty.bus
            
            # Find the booking
            booking = Booking.objects.filter(
                bus=bus,
                seat_number=seat_number,
                status='Confirmed'
            ).first()
            
            if booking:
                # Update status to Cancelled
                booking.status = 'Cancelled'
                booking.save()
                
                # Deactivate the seat segment
                SeatSegment.objects.filter(
                    booking=booking,
                    is_active=True
                ).update(is_active=False)
                
                # Optional: Log cancellation reason
                if cancel_reason:
                    if hasattr(booking, 'notes'):
                        booking.notes = f"{booking.notes}\nCancelled by conductor: {cancel_reason}"
                        booking.save()
                
                messages.success(request, f'✅ Seat {seat_number} booking has been cancelled!')
            else:
                messages.warning(request, f'No active booking found for seat {seat_number}')
            
        except Conductor.DoesNotExist:
            messages.error(request, 'Conductor profile not found')
        except Exception as e:
            messages.error(request, f'Error cancelling booking: {str(e)}')
        
        return redirect('conductor_seat_management', bus_id=bus.id)
    
    return redirect('conductor_dashboard')

from bus_owner.models import BusLiveLocation, RouteStop

@login_required
@require_POST
def update_bus_location(request):
    try:
        conductor = Conductor.objects.get(user=request.user)

        stop_id = request.POST.get('stop_id')

        current_duty = ConductorDuty.objects.filter(
            conductor=conductor,
            is_active=True
        ).first()

        if not current_duty:
            return JsonResponse({'error': 'No assigned bus'}, status=400)

        bus = current_duty.bus

        schedule = BusSchedule.objects.filter(
            bus=bus,
            active=True
        ).first()

        if not schedule:
            return JsonResponse({'error': 'No active schedule'}, status=400)

        stop = RouteStop.objects.get(id=stop_id)

        # 🔥 MAIN LOGIC
        BusLiveLocation.objects.update_or_create(
            bus=bus,
            schedule=schedule,
            defaults={
                'current_stop': stop,
                'updated_by': conductor
            }
        )

        return redirect('conductor_dashboard')

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)