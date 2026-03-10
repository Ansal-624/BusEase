from django.shortcuts import redirect
from django.contrib import messages
from .models import BusOwnerProfile

def owner_approved_required(view_func):
    def wrapper(request, *args, **kwargs):
        try:
            profile = BusOwnerProfile.objects.get(user=request.user)
        except BusOwnerProfile.DoesNotExist:
            messages.error(request, "Complete owner registration first.")
            return redirect('owner_register')

        if not profile.approved:
            messages.warning(request, "Wait for admin approval before accessing this feature.")
            return redirect('owner_dashboard')

        return view_func(request, *args, **kwargs)
    return wrapper
