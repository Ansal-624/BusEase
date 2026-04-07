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


@login_required
def conductor_dashboard(request):
    """Conductor dashboard showing assigned bus and today's duties"""
    try:
        conductor = Conductor.objects.get(user=request.user)
    except Conductor.DoesNotExist:
        messages.error(request, "Conductor profile not found.")
        return redirect('home')
    
    # Get current assigned bus (permanent assignment)
    current_duty = ConductorDuty.objects.filter(
        conductor=conductor,
        is_active=True
    ).first()
    
    assigned_bus = current_duty.bus if current_duty else None
    has_assignment = assigned_bus is not None  # Add this line
    
    # Get today's schedules for the assigned bus
    today = timezone.now().date()
    today_schedules = []
    if assigned_bus:
        today_schedules = BusSchedule.objects.filter(
            bus=assigned_bus,
            departure_time__date=today,
            active=True
        ).select_related('route').order_by('departure_time')
    
    # Get recent bookings for the assigned bus
    recent_bookings = []
    if assigned_bus:
        recent_bookings = Booking.objects.filter(
            bus=assigned_bus
        ).select_related('traveller', 'schedule').order_by('-booking_date')[:10]
    
    context = {
        'conductor': conductor,
        'assigned_bus': assigned_bus,
        'has_assignment': has_assignment,  # Add this
        'today_schedules': today_schedules,
        'recent_bookings': recent_bookings,
        'today': today,
    }
    
    return render(request, 'conductor/dashboard.html', context)


@login_required
def conductor_seat_management(request, bus_id):
    """Conductor seat management page for a specific bus"""
    try:
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
    
    # Get all bookings for this bus (get ALL bookings, not filtered by date)
    # This will show all booked seats regardless of date
    bookings = Booking.objects.filter(
        bus=bus,
        status__in=['Confirmed', 'booked']  # Get both Confirmed and booked status
    ).values_list('seat_number', flat=True)
    
    booked_seats = list(bookings)
    
    # Also check for ConductorBooking if you're using that model
    # If you created ConductorBooking model, include those too
    try:
        from conductor.models import ConductorBooking
        conductor_bookings = ConductorBooking.objects.filter(
            bus=bus,
            status='booked'
        ).values_list('seat_number', flat=True)
        booked_seats.extend(list(conductor_bookings))
        booked_seats = list(set(booked_seats))  # Remove duplicates
    except ImportError:
        pass  # ConductorBooking model doesn't exist yet
    
    # Create seat range
    seat_range = range(1, bus.total_seats + 1)
    
    # Get schedule for fare display
    schedule = BusSchedule.objects.filter(bus=bus, active=True).first()
    
    context = {
        'bus': bus,
        'seat_range': seat_range,
        'booked_seats': booked_seats,
        'seat_status_map': {},
        'total_seats': bus.total_seats,
        'schedule': schedule,
    }
    
    return render(request, 'conductor/seat_management.html', context)

@login_required
def conductor_update_seat_status(request):
    """Update seat status (booked/occupied/cancelled)"""
    if request.method == 'POST':
        try:
            conductor = Conductor.objects.get(user=request.user)
            seat_number = request.POST.get('seat_number')
            passenger_name = request.POST.get('passenger_name')
            passenger_phone = request.POST.get('passenger_phone')
            fare_collected = request.POST.get('fare_collected')
            payment_status = request.POST.get('payment_status')  # 'paid' or 'unpaid'
            status = request.POST.get('status')
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
            
            # Get or create a schedule for this bus
            schedule = BusSchedule.objects.filter(bus=bus, active=True).first()
            
            if not schedule:
                messages.error(request, 'No active schedule found for this bus.')
                return redirect('conductor_dashboard')
            
            # Set payment status for booking
            payment_status_value = 'Paid' if payment_status == 'paid' else 'Pending'
            
            # IMPORTANT: Explicitly set the status field
            booking_status = 'Confirmed'  # Use 'Confirmed' as per your model default
            
            # Check if booking already exists
            existing_booking = Booking.objects.filter(
                bus=bus,
                seat_number=seat_number,
                schedule=schedule
            ).first()
            
            if existing_booking:
                # Update existing booking
                existing_booking.traveller = conductor.user
                existing_booking.total_fare = fare_collected or 0
                existing_booking.status = booking_status  # Explicitly set status
                existing_booking.payment_status = payment_status_value
                existing_booking.payment_amount = fare_collected if payment_status == 'paid' else 0
                existing_booking.save()
                booking = existing_booking
                created = False
            else:
                # Create new booking with ALL required fields
                booking = Booking.objects.create(
                    bus=bus,
                    seat_number=seat_number,
                    schedule=schedule,
                    traveller=conductor.user,
                    total_fare=fare_collected or 0,
                    status=booking_status,  # Explicitly set status
                    payment_status=payment_status_value,
                    payment_amount=fare_collected if payment_status == 'paid' else 0,
                    booking_date=timezone.now()
                )
                created = True
            
            # Store passenger details in a way that persists
            passenger_info = f"Passenger: {passenger_name}, Phone: {passenger_phone}"
            if notes:
                passenger_info += f" | Notes: {notes}"
            
            # If your Booking model has a notes field, save it
            if hasattr(booking, 'notes'):
                booking.notes = passenger_info
                booking.save()
            
            payment_text = "with payment" if payment_status == 'paid' else "without payment"
            messages.success(request, f'✅ Seat {seat_number} booked for {passenger_name} {payment_text}')
            
            # Force redirect to refresh the page with updated data
            return redirect('conductor_seat_management', bus_id=bus.id)
            
        except Conductor.DoesNotExist:
            messages.error(request, 'Conductor profile not found')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            # Print the full error for debugging
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
    """Cancel a booked seat - DELETE the booking"""
    if request.method == 'POST':
        try:
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
            
            # Find and DELETE the booking
            booking = Booking.objects.filter(
                bus=bus,
                seat_number=seat_number
            ).first()
            
            if booking:
                # Optional: Log cancellation reason if you want to track it
                if cancel_reason:
                    # You can print or log this for audit purposes
                    print(f"Seat {seat_number} on bus {bus.bus_number} cancelled by {conductor.user.username}. Reason: {cancel_reason}")
                
                # Delete the booking
                booking.delete()
                messages.success(request, f'✅ Seat {seat_number} booking has been cancelled and is now available!')
            else:
                messages.warning(request, f'No booking found for seat {seat_number}')
            
        except Conductor.DoesNotExist:
            messages.error(request, 'Conductor profile not found')
        except Exception as e:
            messages.error(request, f'Error cancelling booking: {str(e)}')
        
        return redirect('conductor_seat_management', bus_id=bus.id)
    
    return redirect('conductor_dashboard')