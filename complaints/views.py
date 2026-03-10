from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import ComplaintForm
from .models import Complaint

@login_required
def add_complaint(request):
    if request.method == "POST":
        form = ComplaintForm(request.POST, request.FILES)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.traveller = request.user
            complaint.save()
            return redirect("my_complaints")
    else:
        form = ComplaintForm()

    return render(request, "complaints/add_complaint.html", {"form": form})


@login_required
def my_complaints(request):
    complaints = Complaint.objects.filter(traveller=request.user).order_by('-created_at')
    return render(request, 'complaints/my_complaints.html', {
        'complaints': complaints
    })

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.contrib import messages

# Admin - View All Complaints
from django.contrib.admin.views.decorators import staff_member_required
from .models import Complaint

@staff_member_required
def admin_complaints(request):

    complaints = Complaint.objects.all().order_by('-created_at')

    pending_count = Complaint.objects.filter(status="Pending").count()
    checking_count = Complaint.objects.filter(status="Checking").count()
    action_count = Complaint.objects.filter(status="Action").count()

    context = {
        "complaints": complaints,
        "pending_count": pending_count,
        "in_progress_count": checking_count,   # used by template
        "resolved_count": action_count         # used by template
    }

    return render(request, "admin_app/admin_complaints.html", context)


# Admin - Update Complaint Status
@staff_member_required
def update_complaint_status(request, pk):
    complaint = get_object_or_404(Complaint, pk=pk)

    if request.method == "POST":
        new_status = request.POST.get("status")
        note = request.POST.get("admin_note")

        complaint.status = new_status
        complaint.admin_note = note
        complaint.save()

        messages.success(request, "Complaint updated successfully.")
        return redirect("admin_complaints")

    return render(request, "admin_app/update_complaint.html", {
        "complaint": complaint
    })