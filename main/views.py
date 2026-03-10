

# Create your views here.
from django.contrib import messages
from .models import User
from django.contrib.auth import logout
from django.contrib.auth import authenticate,login
from bus_owner.models import BusOwnerProfile
import random
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from .models import PasswordResetOTP
User = get_user_model()
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseBadRequest
from django.urls import reverse
from django.views.decorators.http import require_POST

from reviews.models import AppReview



# main/views.py (update register_view)


def home_view(request):
    reviews = AppReview.objects.order_by("-created_at")[:6]
    return render(request, 'home.html', {'reviews': reviews})



# main/views.py (snippet)


from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth import login   # important

def register_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # Validation list
        errors = []

        # Check if passwords match
        if password != confirm_password:
            errors.append("Passwords do not match")

        # Check if username exists
        if User.objects.filter(username=username).exists():
            errors.append("Username already exists")

        # Check if email exists
        if User.objects.filter(email=email).exists():
            errors.append("Email already registered")

        # Password strength checks
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        
        if not any(char.isupper() for char in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not any(char.isdigit() for char in password):
            errors.append("Password must contain at least one number")

        # If there are errors, show them
        if errors:
            for error in errors:
                messages.error(request, error)
            return redirect('register')  # Back to registration form

        # Create user (NO Traveller model)
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # Auto login after signup
        login(request, user)

        messages.success(request, "Account created successfully!")

        # Go directly to traveller page
        return redirect('traveller_dashboard')

    return render(request, 'main/register.html')



# main/views.py (snippet)


from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.models import User
from django.shortcuts import render, redirect


def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        # 🔎 Check if user exists first
        if not User.objects.filter(username=username).exists():
            messages.error(request, "User does not exist.")
            return render(request, "main/login.html")

        user = authenticate(request, username=username, password=password)

        if user is None:
            messages.error(request, "Invalid password.")
            return render(request, "main/login.html")

        # ✅ Login user
        login(request, user)

        # ✅ Safe role-based redirect
        if user.is_superuser or getattr(user, "role", None) == "admin":
            return redirect("admin_dashboard")

        elif getattr(user, "role", None) == "owner":
            return redirect("owner_dashboard")

        elif getattr(user, "role", None) == "traveller":
            return redirect("traveller_dashboard")

        else:
            messages.warning(request, "No dashboard assigned for this role.")
            return redirect("home")

    return render(request, "main/login.html")




@login_required
def owner_dashboard(request):
    return render(request, 'owner_dashboard.html')
@login_required
def admin_dashboard(request):
    return render(request, 'admin_dashboard.html')
@login_required
def traveller_dashboard(request):
    return render(request, 'traveller/traveller_dashboard.html')

def logout_view(request):
    logout(request)
    return redirect('home')




User = get_user_model()

# Helper: is admin
def is_admin(user):
    # adapt if you use user.role field; or use is_superuser
    return getattr(user, 'is_superuser', False) or getattr(user, 'role', '') == 'admin'

# Inbox (list) view


# Single message view (and mark as read)


# Admin -> send message to a user (simple form)

# Owner reply to an admin message (owner allowed only to reply to messages where recipient is owner and sender is admin)

# Traveller files a complaint (creates a notification to admin)

# AJAX endpoint to fetch unread count and recent items (for navbar bell)

# Mark single notification as read (AJAX or POST)



def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, "No account found with this email.")
            return redirect("forgot_password")

        otp = str(random.randint(1000, 9999))

        PasswordResetOTP.objects.create(
            user=user,
            otp=otp
        )

        send_mail(
            subject="BusEase Password Reset OTP",
            message=f"Your 4-digit OTP is: {otp}\nValid for 5 minutes.",
           from_email="BusEase <noreply@busease.com>",

            recipient_list=[email],
        )

        request.session["reset_user_id"] = user.id
        messages.success(request, "OTP sent to your email.")
        return redirect("verify_otp")

    return render(request, "main/forgot_password.html")


def verify_otp(request):
    user_id = request.session.get("reset_user_id")

    if not user_id:
        return redirect("forgot_password")

    if request.method == "POST":
        otp_input = request.POST.get("otp")

        otp_obj = PasswordResetOTP.objects.filter(
            user_id=user_id,
            otp=otp_input,
            is_used=False
        ).last()

        if not otp_obj:
            messages.error(request, "Invalid OTP.")
            return redirect("verify_otp")

        if otp_obj.is_expired():
            messages.error(request, "OTP expired. Request again.")
            return redirect("forgot_password")

        otp_obj.is_used = True
        otp_obj.save()

        request.session["otp_verified"] = True
        return redirect("reset_password")

    return render(request, "main/verify_otp.html")


def reset_password(request):
    if not request.session.get("otp_verified"):
        return redirect("forgot_password")

    user_id = request.session.get("reset_user_id")
    user = User.objects.get(id=user_id)

    if request.method == "POST":
        password1 = request.POST.get("password1")
        password2 = request.POST.get("password2")

        if password1 != password2:
            messages.error(request, "Passwords do not match.")
            return redirect("reset_password")

        user.password = make_password(password1)
        user.save()

        request.session.flush()
        messages.success(request, "Password reset successful. Please login.")
        return redirect("login")

    return render(request, "main/reset_password.html")


from django.shortcuts import redirect

def dashboard_redirect(request):
    if hasattr(request.user, 'traveller'):
        return redirect('traveller_dashboard')
    elif hasattr(request.user, 'busowner'):
        return redirect('owner_dashboard')
    return redirect('home')
