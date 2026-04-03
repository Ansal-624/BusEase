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
    
    # Get seat status map (you'll need to implement this based on your booking system)
    seat_status_map = {}
    booked_seats = []
    
    # Get all bookings for this bus for today
    today = timezone.now().date()
    bookings = Booking.objects.filter(
        bus=bus,
        journey_date=today
    ).values_list('seat_number', flat=True)
    
    booked_seats = list(bookings)
    
    # Create seat range (assuming seats are numbered 1 to total_seats)
    seat_range = range(1, bus.total_seats + 1)
    
    context = {
        'bus': bus,
        'seat_range': seat_range,
        'booked_seats': booked_seats,
        'seat_status_map': seat_status_map,
        'total_seats': bus.total_seats,
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
            
            # Create or update booking
            booking, created = Booking.objects.update_or_create(
                bus=bus,
                seat_number=seat_number,
                journey_date=timezone.now().date(),
                defaults={
                    'traveller': request.user,
                    'passenger_name': passenger_name,
                    'passenger_phone': passenger_phone,
                    'fare': fare_collected,
                    'status': status,
                    'notes': notes,
                    'booking_date': timezone.now()
                }
            )
            
            messages.success(request, f'Seat {seat_number} marked as {status}')
            return redirect('conductor_seat_management', bus_id=bus.id)
            
        except Conductor.DoesNotExist:
            messages.error(request, 'Conductor profile not found')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
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


@require_POST
@login_required
def conductor_cancel_booking(request, booking_id):
    """Cancel a booking"""
    try:
        conductor = Conductor.objects.get(user=request.user)
        booking = get_object_or_404(Booking, id=booking_id)
        
        # Verify conductor is assigned to this bus
        current_duty = ConductorDuty.objects.filter(
            conductor=conductor,
            bus=booking.bus,
            is_active=True
        ).first()
        
        if not current_duty:
            messages.error(request, "You are not authorized to cancel this booking.")
            return redirect('conductor_dashboard')
        
        booking.status = 'cancelled'
        booking.save()
        
        messages.success(request, f'Booking for seat {booking.seat_number} has been cancelled.')
        
    except Conductor.DoesNotExist:
        messages.error(request, "Conductor profile not found.")
    
    return redirect('conductor_bookings')