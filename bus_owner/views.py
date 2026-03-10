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

    # 🔹 Safely get owner profile
    owner_profile = BusOwnerProfile.objects.filter(user=owner).first()

    # 🚫 If no profile exists
    if not owner_profile:
        messages.error(request, "Your Bus Owner profile is not created yet.")
        return redirect("home")   # or redirect to profile create page

    # 🔹 Get buses of this owner
    buses = Bus.objects.filter(owner=owner_profile)

    # 🔹 Count schedules
    total_schedules = BusSchedule.objects.filter(bus__in=buses).count()

    context = {
        'buses': buses,
        'bus_count': buses.count(),
        'total_schedules': total_schedules,
        'approved': owner_profile.approved,
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



