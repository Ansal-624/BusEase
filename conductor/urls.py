"""
URL configuration for BusEase project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from django.conf import settings
from django.conf.urls.static import static
from . import views
urlpatterns = [
    path('dashboard/', views.conductor_dashboard, name='conductor_dashboard'),
    path('seat-management/<int:bus_id>/', views.conductor_seat_management, name='conductor_seat_management'),
    path('update-seat-status/', views.conductor_update_seat_status, name='conductor_update_seat_status'),
    path('duty/current/', views.conductor_current_duty, name='conductor_current_duty'),
    path('schedules/', views.conductor_schedules, name='conductor_schedules'),
    path('bookings/', views.conductor_bookings, name='conductor_bookings'),
    path('cancel-booking/<int:booking_id>/', views.conductor_cancel_booking, name='conductor_cancel_booking'),
]



# if settings.DEBUG:
#     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
