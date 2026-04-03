from django.shortcuts import render, redirect, get_object_or_404,HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from main.models import User
from .models import Bus, BusOwnerProfile, Route, RouteStop, BusSchedule
from datetime import datetime
from django.views.decorators.http import require_POST
from traveller.models import Booking
from .models import Bus, BusPhoto
from .decorators import owner_approved_required





# 🧍‍♂️ Extra details for owner registration
# @login_required  # ✅ ensure user is logged in
# def owner_register_extra(request):
#     if request.method == 'POST':
#         contact_number = request.POST.get('contact_number')
#         address = request.POST.get('address')
#         owner_photo = request.FILES.get('owner_photo')
#         business_license = request.FILES.get('business_license')
#         id_proof = request.FILES.get('id_proof')

#         # ✅ Check if this user already has a profile
#         if BusOwnerProfile.objects.filter(user=request.user).exists():
#             messages.warning(request, "You have already completed your owner registration.")
#             return redirect('owner_dashboard')

#         # ✅ Create owner profile safely
#         BusOwnerProfile.objects.create(
#             user=request.user,
#             contact_number=contact_number,
#             address=address,
#             owner_photo=owner_photo,
#             business_license=business_license,
#             id_proof=id_proof
#         )

#         messages.success(request, "Owner registration completed successfully.")
#         return redirect('owner_dashboard')

#     return render(request, 'bus_owner/owner_register_extra.html')

from django.shortcuts import render, redirect
from django.contrib import messages
from .models import BusOwnerProfile
from django.contrib.auth import login
from django.contrib.auth import get_user_model
User = get_user_model()


def owner_register(request):
    if request.method == "POST":

        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")

        contact = request.POST.get("contact_number")
        address = request.POST.get("address")
        photo = request.FILES.get("owner_photo")
        license_file = request.FILES.get("business_license")
        id_file = request.FILES.get("id_proof")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
            return redirect("owner_register")

        # ✅ create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role="owner"
        )

        # ✅ create profile
        BusOwnerProfile.objects.create(
            user=user,
            contact_number=contact,
            address=address,
            owner_photo=photo,
            business_license=license_file,
            id_proof=id_file,
            approved=False
        )

        # ✅ AUTO LOGIN (IMPORTANT)
        login(request, user)

        messages.success(request, "Registered successfully. Waiting for admin approval.")
        return redirect("owner_dashboard")

    return render(request, "bus_owner/owner_register.html")

# 🏠 Owner dashboard


# from .models import Bus, Schedule   # 👉 Make sure Schedule is imported

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from .models import BusOwnerProfile, Bus, BusSchedule


from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import BusOwnerProfile, Bus, BusSchedule


@login_required
def owner_dashboard(request):
    owner = request.user

    # Get owner profile
    owner_profile = BusOwnerProfile.objects.filter(user=owner).first()

    if not owner_profile:
        messages.error(request, "Your Bus Owner profile is not created yet.")
        return redirect("home")

    # Get buses
    buses = Bus.objects.filter(owner=owner_profile)
    
    # Get conductors
    conductors = Conductor.objects.filter(owner=owner_profile)
    
    # Count active duties (conductors assigned to buses) - FIXED: removed duty_date
    from django.utils import timezone
    today = timezone.now().date()
    
    active_duties = ConductorDuty.objects.filter(
        conductor__owner=owner_profile,
        is_active=True
    ).count()
    
    # Count on duty today (same as active duties for permanent assignment)
    on_duty_today = active_duties
    
    # Count available buses (approved buses without assigned conductors)
    assigned_bus_ids = ConductorDuty.objects.filter(
        conductor__owner=owner_profile,
        is_active=True
    ).values_list('bus_id', flat=True)
    
    available_buses = buses.filter(approved=True).exclude(id__in=assigned_bus_ids).count()

    # Count schedules
    total_schedules = BusSchedule.objects.filter(bus__in=buses).count()
    
    # Count approved buses
    approved_buses_count = buses.filter(approved=True).count()

    context = {
        # Fleet stats
        'buses': buses,
        'bus_count': buses.count(),
        'total_schedules': total_schedules,
        'approved_buses_count': approved_buses_count,
        
        # Conductor stats
        'conductors': conductors,
        'total_conductors': conductors.count(),
        'active_conductors': conductors.filter(is_active=True).count(),
        
        # Duty stats
        'active_duties': active_duties,
        'on_duty_today': on_duty_today,
        'available_buses': available_buses,
        
        # Approval status
        'approved': owner_profile.approved,
        
        # Today's date for forms
        'today': today,
    }

    return render(request, 'bus_owner/owner_dashboard.html', context)


@login_required
@owner_approved_required
def add_bus(request):
    try:
        owner_profile = BusOwnerProfile.objects.get(user=request.user)
    except BusOwnerProfile.DoesNotExist:
        messages.error(request, "You need to complete your owner registration first.")
        return redirect('owner_register_extra')

    if request.method == "POST":
        bus_name = request.POST.get('bus_name')
        bus_number = request.POST.get('bus_number')
        total_seats = request.POST.get('total_seats')
        owner_contact_number = request.POST.get('owner_contact_number')
        driver_name = request.POST.get('driver_name')
        driver_contact_number = request.POST.get('driver_contact_number')
        driver_license = request.FILES.get('driver_license')
        registration_document = request.FILES.get('registration_document')
        pollution_test_certificate = request.FILES.get('pollution_test_certificate')
        insurance_document = request.FILES.get('insurance_document')

        # New: multiple photos
        bus_photos = request.FILES.getlist('bus_photos')

        # Basic validation
        if not bus_name or not bus_number or not total_seats:
            messages.error(request, "Please fill in all required fields.")
            return redirect('add_bus')

        if Bus.objects.filter(bus_number=bus_number).exists():
            messages.error(request, "A bus with this number already exists.")
            return redirect('add_bus')

        # Save main bus record
        bus = Bus.objects.create(
            owner=owner_profile,
            bus_name=bus_name,
            bus_number=bus_number,
            total_seats=total_seats,
            owner_contact_number=owner_contact_number,
            driver_name=driver_name,
            driver_contact_number=driver_contact_number,
            driver_license=driver_license,
            registration_document=registration_document,
            pollution_test_certificate=pollution_test_certificate,
            insurance_document=insurance_document,
        )

        # Save uploaded bus photos
        for photo in bus_photos:
            BusPhoto.objects.create(bus=bus, image=photo)

        messages.success(request, "Bus registration submitted for approval.")
        return redirect('view_buses')

    return render(request, 'bus_owner/add_bus.html')

# 🧾 View all buses owned by the logged-in owner
@login_required
def view_buses(request):
    try:
        owner_profile = BusOwnerProfile.objects.get(user=request.user)
    except BusOwnerProfile.DoesNotExist:
        return redirect('owner_register_extra')

    buses = Bus.objects.filter(owner=owner_profile).prefetch_related('schedules__route__stops')
    return render(request, 'bus_owner/buses.html', {'buses': buses})


# 📊 View the approval status of buses
@login_required
def bus_status(request):
    try:
        owner_profile = BusOwnerProfile.objects.get(user=request.user)
    except BusOwnerProfile.DoesNotExist:
        return redirect('owner_register_extra')

    buses = Bus.objects.filter(owner=owner_profile)
    
    # Count approved and pending buses
    approved_count = buses.filter(approved=True).count()
    pending_count = buses.filter(approved=False).count()
    
    return render(request, 'bus_owner/bus_status.html', {
        'buses': buses,
        'approved_count': approved_count,
        'pending_count': pending_count,
    })

# 🕒 Add a schedule to a specific bus

def parse_time_string(time_str):
    """Utility function to safely parse time input from form."""
    if not time_str:
        return None
    try:
        # Handles 'HH:MM' (time inputs)
        return datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        try:
            # Handles 'YYYY-MM-DDTHH:MM' (datetime-local inputs)
            return datetime.strptime(time_str, "%Y-%m-%dT%H:%M").time()
        except ValueError:
            return None


import json
from django.utils.dateparse import parse_datetime
from django.db import transaction
from django.contrib import messages
from .utils import calculate_distance

import json
from django.utils.dateparse import parse_datetime
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.db import transaction
from .models import Route, RouteStop, BusSchedule
from .utils import calculate_distance


from django.utils import timezone
from datetime import datetime
from django.db import transaction
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
import json


@login_required
def add_schedule(request, bus_id):

    bus = get_object_or_404(Bus, id=bus_id, owner__user=request.user)

    if request.method == "POST":

        start_location = request.POST.get('start_location')
        end_location = request.POST.get('end_location')
        fare_per_km = request.POST.get('fare')
        journey_date = request.POST.get('journey_date')
        route_data_json = request.POST.get("route_data")

        if not route_data_json:
            messages.error(request, "Please select route on map.")
            return redirect('add_schedule', bus_id=bus.id)

        route_points = json.loads(route_data_json)

        if len(route_points) < 2:
            messages.error(request, "At least 2 stops required.")
            return redirect('add_schedule', bus_id=bus.id)

        # ✅ Validate stop data
        for stop in route_points:
            if not stop.get("stop_name") or not stop.get("arrival_time"):
                messages.error(request, "Please fill stop name and arrival time for all stops.")
                return redirect('add_schedule', bus_id=bus.id)

        # ✅ Calculate distance
        distance_input = [
            {"lat": p["lat"], "lng": p["lng"]}
            for p in route_points
        ]
        total_distance = calculate_distance(distance_input)

        try:
            fare_per_km = float(fare_per_km)
        except (TypeError, ValueError):
            messages.error(request, "Invalid fare value.")
            return redirect('add_schedule', bus_id=bus.id)

        total_fare = round(total_distance * fare_per_km, 2)

        # ✅ Create datetime using first & last stop time
        try:
            first_stop_time = route_points[0]["arrival_time"]
            last_stop_time = route_points[-1]["arrival_time"]

            departure_datetime = datetime.strptime(
                f"{journey_date} {first_stop_time}",
                "%Y-%m-%d %H:%M"
            )

            arrival_datetime = datetime.strptime(
                f"{journey_date} {last_stop_time}",
                "%Y-%m-%d %H:%M"
            )

        except Exception:
            messages.error(request, "Invalid date or time format.")
            return redirect('add_schedule', bus_id=bus.id)

        with transaction.atomic():

            # ✅ Create Route
            route = Route.objects.create(
                route_name=f"{start_location} to {end_location}",
                start_location=start_location,
                end_location=end_location,
                route_path=route_points,
                distance_km=total_distance
            )

            # ✅ Create Stops
            for index, point in enumerate(route_points):

                stop_name = (
                    start_location if index == 0
                    else end_location if index == len(route_points) - 1
                    else point["stop_name"]
                )

                RouteStop.objects.create(
                    route=route,
                    stop_name=stop_name,
                    latitude=point["lat"],
                    longitude=point["lng"],
                    arrival_time=point["arrival_time"],
                    order=index + 1
                )

            # ✅ Create Schedule (NOW WITH DATETIME)
            BusSchedule.objects.create(
                bus=bus,
                route=route,
                departure_time=departure_datetime,
                arrival_time=arrival_datetime,
                fare=total_fare
            )

        messages.success(request, "Schedule added successfully.")
        return redirect('view_buses')

    return render(request, 'bus_owner/add_schedule.html', {'bus': bus})
@require_POST
@login_required
def delete_bus(request, bus_id):
    bus = get_object_or_404(Bus, id=bus_id, owner__user=request.user)
    bus.delete()
    messages.success(request, f"Bus {bus.bus_number} and its schedules have been deleted.")
    return redirect('view_buses')


@require_POST
@login_required
def delete_schedule(request, schedule_id):
    schedule = get_object_or_404(BusSchedule, id=schedule_id, bus__owner__user=request.user)
    schedule.delete()
    messages.success(request, "Schedule deleted successfully.")
    return redirect('view_buses')




@login_required
def view_bookings(request, bus_id):
    # Ensure only the bus owner can view this bus’s bookings
    bus = get_object_or_404(Bus, id=bus_id, owner__user=request.user)

    # Fetch all bookings for this bus
    bookings = (
        Booking.objects.filter(bus=bus)
        .select_related("from_stop", "to_stop", "schedule", "traveller")
        .order_by("-booking_date")
    )

    return render(request, "bus_owner/view_bookings.html", {
        "bus": bus,
        "bookings": bookings,
    })


@login_required
def bus_details(request, bus_id):
    bus = get_object_or_404(Bus, id=bus_id, owner__user=request.user)
    photos = BusPhoto.objects.filter(bus=bus)
    return render(request, 'bus_owner/bus_details.html', {'bus': bus, 'photos': photos})

@login_required
def bus_schedules(request):
    owner = request.user

    # fetch all buses owned by the logged-in owner
    buses = Bus.objects.filter(owner__user=owner)

    # fetch all schedules of those buses
    schedules = BusSchedule.objects.filter(bus__in=buses).select_related('bus', 'route')

    context = {
        'buses': buses,
        'schedules': schedules,
    }
    return render(request, 'bus_owner/bus_schedules.html', context)


from django.contrib.auth.models import User
from .models import Conductor, ConductorDuty

# ==============================
# CONDUCTOR MANAGEMENT
# ==============================

@login_required
def owner_conductors_list(request):
    """Bus owner views all their conductors"""
    try:
        owner_profile = BusOwnerProfile.objects.get(user=request.user)
    except BusOwnerProfile.DoesNotExist:
        messages.error(request, "Your Bus Owner profile is not created yet.")
        return redirect('owner_dashboard')
    
    conductors = Conductor.objects.filter(owner=owner_profile).order_by('-created_at')
    
    context = {
        'conductors': conductors,
        'total_conductors': conductors.count(),
        'active_conductors': conductors.filter(is_active=True).count(),
    }
    
    return render(request, 'bus_owner/owner_conductors.html', context)

from main.models import User  # Import your custom User model

@login_required
def owner_add_conductor(request):
    """Bus owner adds a new conductor"""
    try:
        owner_profile = BusOwnerProfile.objects.get(user=request.user)
    except BusOwnerProfile.DoesNotExist:
        messages.error(request, "Your Bus Owner profile is not created yet.")
        return redirect('owner_dashboard')
    
    if not owner_profile.approved:
        messages.error(request, "Your account must be approved before adding conductors.")
        return redirect('owner_dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        
        # Validation
        errors = []
        
        if not all([username, password, email, first_name, last_name, phone]):
            errors.append("All required fields must be filled.")
        
        if password != confirm_password:
            errors.append("Passwords do not match.")
        
        if User.objects.filter(username=username).exists():
            errors.append("Username already exists.")
        
        if User.objects.filter(email=email).exists():
            errors.append("Email already registered.")
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('owner_add_conductor')
        
        try:
            # Create user account with role='conductor'
            user = User.objects.create_user(
                username=username,
                password=password,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role='conductor'  # Changed from 'traveller' to 'conductor'
            )
            
            # Create conductor profile
            conductor = Conductor.objects.create(
                user=user,
                owner=owner_profile,
                phone=phone,
                address=address,
                is_active=True
            )
            
            # Handle profile photo upload
            if request.FILES.get('profile_photo'):
                conductor.profile_photo = request.FILES['profile_photo']
                conductor.save()
            
            messages.success(
                request, 
                f"Conductor {user.get_full_name()} created successfully! Employee ID: {conductor.employee_id}"
            )
            return redirect('owner_conductors_list')
            
        except Exception as e:
            messages.error(request, f"Error creating conductor: {str(e)}")
            return redirect('owner_add_conductor')
    
    return render(request, 'bus_owner/owner_add_conductor.html')

@login_required
def owner_edit_conductor(request, conductor_id):
    """Bus owner edits conductor details"""
    try:
        owner_profile = BusOwnerProfile.objects.get(user=request.user)
    except BusOwnerProfile.DoesNotExist:
        messages.error(request, "Your Bus Owner profile is not created yet.")
        return redirect('owner_dashboard')
    
    conductor = get_object_or_404(Conductor, id=conductor_id, owner=owner_profile)
    user = conductor.user
    
    if request.method == 'POST':
        # Update user details
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        user.email = request.POST.get('email', user.email)
        user.save()
        
        # Update conductor details
        conductor.phone = request.POST.get('phone', conductor.phone)
        conductor.address = request.POST.get('address', conductor.address)
        conductor.is_active = request.POST.get('is_active') == 'on'
        
        if request.FILES.get('profile_photo'):
            conductor.profile_photo = request.FILES['profile_photo']
        
        conductor.save()
        
        # Update password if provided
        new_password = request.POST.get('new_password')
        if new_password:
            user.set_password(new_password)
            user.save()
            messages.info(request, "Password updated successfully. The conductor will need to log in with the new password.")
        
        messages.success(request, f"Conductor {user.get_full_name()} updated successfully!")
        return redirect('owner_conductors_list')
    
    context = {
        'conductor': conductor,
        'user': user,
    }
    return render(request, 'bus_owner/owner_edit_conductor.html', context)

@login_required
def owner_delete_conductor(request, conductor_id):
    """Bus owner deletes a conductor"""
    try:
        owner_profile = BusOwnerProfile.objects.get(user=request.user)
    except BusOwnerProfile.DoesNotExist:
        messages.error(request, "Your Bus Owner profile is not created yet.")
        return redirect('owner_dashboard')
    
    conductor = get_object_or_404(Conductor, id=conductor_id, owner=owner_profile)
    
    if request.method == 'POST':
        user = conductor.user
        conductor_name = user.get_full_name() or user.username
        conductor.delete()
        user.delete()  # Also delete the user account
        messages.success(request, f"Conductor {conductor_name} deleted successfully!")
        return redirect('owner_conductors_list')
    
    return render(request, 'bus_owner/owner_delete_conductor.html', {'conductor': conductor})


@login_required
def owner_assign_duty(request):
    """Bus owner assigns conductor to a bus (permanent assignment)"""
    try:
        owner_profile = BusOwnerProfile.objects.get(user=request.user)
    except BusOwnerProfile.DoesNotExist:
        messages.error(request, "Your Bus Owner profile is not created yet.")
        return redirect('owner_dashboard')
    
    if not owner_profile.approved:
        messages.error(request, "Your account must be approved before assigning conductors.")
        return redirect('owner_dashboard')
    
    if request.method == 'POST':
        conductor_id = request.POST.get('conductor')
        bus_id = request.POST.get('bus')
        
        if not conductor_id or not bus_id:
            messages.error(request, "Please select both conductor and bus.")
            return redirect('owner_assign_duty')
        
        conductor = get_object_or_404(Conductor, id=conductor_id, owner=owner_profile)
        bus = get_object_or_404(Bus, id=bus_id, owner=owner_profile)
        
        # Check if conductor already has an assigned bus
        existing_assignment = ConductorDuty.objects.filter(conductor=conductor, is_active=True).first()
        
        if existing_assignment:
            # Update existing assignment
            existing_assignment.bus = bus
            existing_assignment.assigned_by = request.user
            existing_assignment.save()
            messages.success(
                request, 
                f"Conductor {conductor.user.get_full_name()} reassigned to {bus.bus_name} ({bus.bus_number})"
            )
        else:
            # Create new assignment
            ConductorDuty.objects.create(
                conductor=conductor,
                bus=bus,
                assigned_by=request.user,
                is_active=True
            )
            messages.success(
                request, 
                f"Conductor {conductor.user.get_full_name()} assigned to {bus.bus_name} ({bus.bus_number})"
            )
        
        return redirect('owner_conductors_list')
    
    # GET request - get data for form
    conductors = Conductor.objects.filter(owner=owner_profile, is_active=True)
    buses = Bus.objects.filter(owner=owner_profile, approved=True)
    
    # Get current assignments
    assignments = {duty.conductor_id: duty.bus_id for duty in ConductorDuty.objects.filter(
        conductor__owner=owner_profile, is_active=True
    )}
    
    context = {
        'conductors': conductors,
        'buses': buses,
        'assignments': assignments,
    }
    return render(request, 'bus_owner/owner_assign_duty.html', context)


@login_required
def owner_unassign_conductor(request, conductor_id):
    """Bus owner removes conductor from bus assignment"""
    try:
        owner_profile = BusOwnerProfile.objects.get(user=request.user)
    except BusOwnerProfile.DoesNotExist:
        messages.error(request, "Your Bus Owner profile is not created yet.")
        return redirect('owner_dashboard')
    
    conductor = get_object_or_404(Conductor, id=conductor_id, owner=owner_profile)
    
    if request.method == 'POST':
        # Get the assignment and delete it
        assignment = ConductorDuty.objects.filter(conductor=conductor, is_active=True).first()
        
        if assignment:
            assignment.delete()  # This removes the assignment entirely
            messages.success(request, f"Conductor {conductor.user.get_full_name()} has been unassigned from their bus.")
        else:
            messages.warning(request, "This conductor is not assigned to any bus.")
        
        return redirect('owner_conductors_list')
    
    # GET request - show confirmation page
    context = {
        'conductor': conductor,
        'assigned_bus': conductor.assigned_bus,
    }
    return render(request, 'bus_owner/owner_unassign_conductor.html', context)


@login_required
def owner_duty_assignments(request):
    """Bus owner views all duty assignments"""
    try:
        owner_profile = BusOwnerProfile.objects.get(user=request.user)
    except BusOwnerProfile.DoesNotExist:
        messages.error(request, "Your Bus Owner profile is not created yet.")
        return redirect('owner_dashboard')
    
    duties = ConductorDuty.objects.filter(
        conductor__owner=owner_profile
    ).select_related('conductor', 'bus', 'schedule').order_by('-duty_date', '-start_time')
    
    # Filter by status
    from django.utils import timezone
    today = timezone.now().date()
    status = request.GET.get('status', 'all')
    
    if status == 'upcoming':
        duties = duties.filter(duty_date__gte=today)
    elif status == 'past':
        duties = duties.filter(duty_date__lt=today)
    elif status == 'today':
        duties = duties.filter(duty_date=today)
    
    context = {
        'duties': duties,
        'status': status,
        'today': today,
    }
    return render(request, 'bus_owner/owner_duties.html', context)


@login_required
def owner_cancel_duty(request, duty_id):
    """Bus owner cancels a duty assignment"""
    try:
        owner_profile = BusOwnerProfile.objects.get(user=request.user)
    except BusOwnerProfile.DoesNotExist:
        messages.error(request, "Your Bus Owner profile is not created yet.")
        return redirect('owner_dashboard')
    
    duty = get_object_or_404(ConductorDuty, id=duty_id, conductor__owner=owner_profile)
    
    if request.method == 'POST':
        duty.is_active = False
        duty.save()
        messages.success(request, f"Duty for {duty.conductor.user.username} on {duty.bus.bus_number} cancelled!")
        return redirect('owner_duty_assignments')
    
    return render(request, 'bus_owner/owner_cancel_duty.html', {'duty': duty})
