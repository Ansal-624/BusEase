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
from django.urls import path
from . import views
from main.views import login_view, register_view


urlpatterns = [
   
      path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),

    # Traveller Dashboard from traveller/views.py
    path('dashboard/', views.traveller_dashboard, name='traveller_dashboard'),

    path('apply-concession/', views.apply_concession, name='apply_concession'),
    path('book/<int:schedule_id>/', views.book_bus, name='book_bus'),
    path('bus/<int:bus_id>/schedules/', views.view_schedules, name='view_schedules'),
    path('track/<int:bus_id>/', views.track_bus, name='track_bus'),
    path('view_concession_card/<int:concession_id>/', views.view_concession_card, name='view_concession_card'),

    # 🔎 Search Buses
    path("search-buses/", views.search_buses, name="search_buses"),
    path('available-buses/',views.available_buses, name='available_buses'),
    path('bookings/',views.traveller_bookings_page, name='traveller_bookings_page'),
    path(
    "ticket/download/<int:booking_id>/",
    views.download_ticket,
    name="download_ticket"
    ),
    
    path(
        "ticket/<int:booking_id>/",
        views.view_ticket,
        name="view_ticket"
    ),
    path(
        "ticket/<int:booking_id>/pdf/",
        views.download_ticket_pdf,
        name="download_ticket_pdf"
    ),
    path("track-bus/", views.track_bus_list, name="track_bus_list"),

    path('create-razorpay-order/', views.create_razorpay_order, name='create_razorpay_order'),
    path('verify-payment/', views.verify_payment, name='verify_payment'),
]


