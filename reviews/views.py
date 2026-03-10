from django.shortcuts import render

# Create your views here.
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import AppReviewForm

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .forms import AppReviewForm

@login_required
def add_app_review(request):
    if request.method == "POST":
        form = AppReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            review.save()
            print("Review saved!", review)
            # ✅ Redirect based on role
            if hasattr(request.user, "travellerprofile"):
                return redirect("traveller_dashboard")
            elif hasattr(request.user, "ownerprofile"):
                return redirect("owner_dashboard")
            else:
                return redirect("home")
    else:
        form = AppReviewForm()

    return render(request, "reviews/add_app_review.html", {"form": form})


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from bus_owner.models import Bus
from .models import BusReview
from .forms import BusReviewForm

@login_required
def add_bus_review(request, bus_id):
    bus = get_object_or_404(Bus, id=bus_id)

    # if user already reviewed, edit instead of create
    review = BusReview.objects.filter(bus=bus, traveller=request.user).first()

    if request.method == "POST":
        form = BusReviewForm(request.POST, instance=review)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.bus = bus
            obj.traveller = request.user
            obj.save()
            return redirect('view_schedules', bus_id=bus.id)

    else:
        form = BusReviewForm(instance=review)

    return render(request, "reviews/add_bus_review.html", {
        "form": form,
        "bus": bus
    })
