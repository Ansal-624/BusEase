from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.contrib.admin.views.decorators import staff_member_required

from bus_owner.models import Bus, BusSchedule
from traveller.models import Booking, ConcessionApplication, ConcessionDetail, ECard


# ============================================================
# 🛡️ Superuser Check
# ============================================================

def superuser_required(user):
    return user.is_superuser


# ============================================================
# 📊 DASHBOARD
# ============================================================

from complaints.models import Complaint   # ✅ Import this model



from bus_owner.models import BusOwnerProfile

@login_required
@user_passes_test(superuser_required)
def admin_dashboard(request):

    context = {
        "pending_buses_count": Bus.objects.filter(approved=False).count(),
        "approved_buses_count": Bus.objects.filter(approved=True).count(),

        "pending_concessions_count": ConcessionApplication.objects.filter(status="Pending").count(),
        "approved_concessions_count": ConcessionApplication.objects.filter(status="Approved").count(),

        "pending_complaints": Complaint.objects.filter(status="Pending").count(),
        "checking_complaints": Complaint.objects.filter(status="Checking").count(),
        "resolved_complaints": Complaint.objects.filter(status="Resolved").count(),

        # NEW
        "pending_bus_owners": BusOwnerProfile.objects.filter(approved=False).count(),
        "approved_bus_owners": BusOwnerProfile.objects.filter(approved=True).count(),
    }

    return render(request, "admin_app/admin_dashboard.html", context)


@staff_member_required
def approve_bus_owner(request, owner_id):

    owner = BusOwnerProfile.objects.get(id=owner_id)
    owner.approved = True
    owner.save()

    return redirect("admin_bus_owner_requests")


from bus_owner.models import BusOwnerProfile
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render


@staff_member_required
def admin_bus_owner_requests(request):

    owners = BusOwnerProfile.objects.filter(approved=False)

    return render(request, "admin_app/bus_owner_requests.html", {
        "owners": owners
    })


@staff_member_required
def admin_approved_bus_owners(request):

    owners = BusOwnerProfile.objects.filter(approved=True)

    return render(request, "admin_app/approved_bus_owners.html", {
        "owners": owners
    })
# ============================================================
# 🚌 BUS MANAGEMENT
# ============================================================

# 🔹 Pending Bus Approvals
@login_required
@user_passes_test(superuser_required)
def admin_bus_approvals(request):
    pending_buses = Bus.objects.filter(approved=False).select_related("owner", "owner__user")

    return render(request, "admin_app/admin_bus_approvals.html", {
        "pending_buses": pending_buses
    })


# 🔹 Approved Buses
@login_required
@user_passes_test(superuser_required)
def admin_approved_buses(request):
    approved_buses = Bus.objects.filter(approved=True)

    return render(request, "admin_app/admin_approved_buses.html", {
        "approved_buses": approved_buses
    })


# 🔹 Approve Bus
@login_required
@user_passes_test(superuser_required)
def approve_bus(request, bus_id):
    bus = get_object_or_404(Bus, id=bus_id)
    bus.approved = True
    bus.save()

    messages.success(request, f"Bus '{bus.bus_number}' approved successfully.")
    return redirect("admin_bus_approvals")


# 🔹 Reject Bus
@login_required
@user_passes_test(superuser_required)
def reject_bus(request, bus_id):
    bus = get_object_or_404(Bus, id=bus_id)
    bus.delete()

    messages.warning(request, f"Bus '{bus.bus_number}' rejected and removed.")
    return redirect("admin_bus_approvals")


# ============================================================
# 🎓 CONCESSION MANAGEMENT
# ============================================================

# 🔹 Pending Concessions
@login_required
@user_passes_test(superuser_required)
def admin_concessions(request):
    pending_concessions = ConcessionApplication.objects.filter(status="Pending")

    return render(request, "admin_app/admin_concessions.html", {
        "pending_concessions": pending_concessions
    })


# 🔹 Approved Concessions
@login_required
@user_passes_test(superuser_required)
def admin_approved_concessions(request):
    approved_concessions = ConcessionApplication.objects.filter(status="Approved")

    return render(request, "admin_app/admin_approved_concessions.html", {
        "approved_concessions": approved_concessions
    })


# 🔹 Approve Concession
@login_required
@user_passes_test(superuser_required)
def approve_concession(request, concession_id):

    concession = get_object_or_404(ConcessionApplication, id=concession_id)
    traveller = concession.traveller

    # 🔎 Check existing ECard
    ecard = ECard.objects.filter(traveller=traveller).first()

    if ecard:
        ConcessionDetail.objects.filter(ecard=ecard).delete()
        ecard.active = True
        ecard.valid_till = timezone.now().date() + timedelta(days=365)
        ecard.save()
    else:
        ecard = ECard.objects.create(
            traveller=traveller,
            card_id=f"EC{traveller.id:05}",
            valid_till=timezone.now().date() + timedelta(days=365),
            active=True
        )

    # 🆕 Create Concession Detail
    ConcessionDetail.objects.create(
        application=concession,
        traveller=traveller,
        ecard=ecard,
        college_name=concession.college_name,
        starting_location=concession.starting_location,
        ending_location=concession.ending_location,
        concession_percentage=50,
        valid_from=timezone.now().date(),
        valid_till=timezone.now().date() + timedelta(days=180),
    )

    concession.status = "Approved"
    concession.approved_on = timezone.now()
    concession.save()

    messages.success(request, f"Concession approved. E-Card issued to {traveller.username}")
    return redirect("admin_concessions")


# 🔹 Reject Concession
@login_required
@user_passes_test(superuser_required)
def reject_concession(request, concession_id):

    concession = get_object_or_404(ConcessionApplication, id=concession_id)

    if request.method == "POST":
        reason = request.POST.get("reason")

        ConcessionDetail.objects.filter(application=concession).delete()
        ECard.objects.filter(traveller=concession.traveller).update(active=False)

        concession.status = "Rejected"
        concession.cancel_reason = reason
        concession.save()

        messages.warning(request, f"Concession rejected: {reason}")
        return redirect("admin_concessions")

    return render(request, "admin_app/reject_concession_form.html", {
        "concession": concession
    })


# 🔹 Cancel Concession
@login_required
@user_passes_test(superuser_required)
def cancel_concession(request, concession_id):

    concession = get_object_or_404(ConcessionApplication, id=concession_id)

    if request.method == "POST":
        reason = request.POST.get("reason")

        ConcessionDetail.objects.filter(application=concession).delete()
        ECard.objects.filter(traveller=concession.traveller).update(active=False)

        concession.status = "Cancelled"
        concession.cancel_reason = reason
        concession.save()

        messages.error(request, f"Concession cancelled: {reason}")
        return redirect("admin_approved_concessions")

    return render(request, "admin_app/cancel_concession_form.html", {
        "concession": concession
    })


# 🔹 View Concession Details
@login_required
@user_passes_test(superuser_required)
def admin_view_concession_details(request, concession_id):

    concession = get_object_or_404(ConcessionApplication, id=concession_id)

    return render(request, "admin_app/concession_details.html", {
        "concession": concession
    })


# ============================================================
# 🕒 BUS SCHEDULES
# ============================================================

@login_required
@user_passes_test(superuser_required)
def admin_view_schedules(request, bus_id):

    bus = get_object_or_404(Bus, id=bus_id)
    schedules = BusSchedule.objects.filter(bus=bus)

    return render(request, "admin_app/admin_view_schedules.html", {
        "bus": bus,
        "schedules": schedules
    })


# ============================================================
# 🎟️ BOOKINGS
# ============================================================

@login_required
@user_passes_test(superuser_required)
def admin_view_bookings(request, bus_id):

    bus = get_object_or_404(Bus, id=bus_id)
    bookings = Booking.objects.filter(bus=bus)

    return render(request, "admin_app/admin_view_bookings.html", {
        "bus": bus,
        "bookings": bookings
    })


# ============================================================
# 📂 BUS DOCUMENTS
# ============================================================

@login_required
@user_passes_test(superuser_required)
def admin_view_bus_documents(request, bus_id):

    bus = get_object_or_404(Bus, id=bus_id)
    photos = bus.photos.all()

    return render(request, "admin_app/bus_documents.html", {
        "bus": bus,
        "photos": photos
    })


# ============================================================
# 🔔 PENDING UPDATES PAGE
# ============================================================

@login_required
@user_passes_test(superuser_required)
def pending_updates(request):
    return render(request, "admin_app/pending_updates.html")



@staff_member_required
def complaints_by_status(request, status):
    complaints = Complaint.objects.filter(status=status).order_by('-created_at')

    return render(request, "admin_app/complaints_by_status.html", {
        "complaints": complaints,
        "status": status
    })