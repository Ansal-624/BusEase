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
from . import views as admin_views


urlpatterns = [
   # 🏠 Dashboard
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),

    # 🚍 Pending Bus Approvals
    path('bus-approvals/', views.admin_bus_approvals, name='admin_bus_approvals'),

    # ✅ Approved Buses
    path('approved-buses/', views.admin_approved_buses, name='admin_approved_buses'),

    # 📂 Bus Documents
    path('bus/<int:bus_id>/documents/', views.admin_view_bus_documents, name='admin_view_bus_documents'),

    # ✔ Approve / Reject Bus
    path('bus/<int:bus_id>/approve/', views.approve_bus, name='approve_bus'),
    path('bus/<int:bus_id>/reject/', views.reject_bus, name='reject_bus'),

    # 🎓 Pending Concessions
    path('concessions/', views.admin_concessions, name='admin_concessions'),

    # ✅ Approved Concessions
    path('approved-concessions/', views.admin_approved_concessions, name='admin_approved_concessions'),

    # ✔ Approve / Reject Concession
    path('concession/<int:id>/approve/', views.approve_concession, name='approve_concession'),
    path('concession/<int:id>/reject/', views.reject_concession, name='reject_concession'),

    # 📄 Concession Details
    path('concession/<int:concession_id>/details/', views.admin_view_concession_details, name='admin_view_concession_details'),

    # ❌ Cancel Approved Concession
    path('concession/<int:id>/cancel/', views.cancel_concession, name='cancel_concession'),

    # 🗓 View Schedules
    path('bus/<int:bus_id>/schedules/', views.admin_view_schedules, name='admin_view_schedules'),

    # 👥 View Bookings
    path('bus/<int:bus_id>/bookings/', views.admin_view_bookings, name='admin_view_bookings'),
    path(
    "admin/complaints/status/<str:status>/",
    views.complaints_by_status,
    name="complaints_by_status"
),
path("bus-owner-requests/", views.admin_bus_owner_requests, name="admin_bus_owner_requests"),
path("approved-bus-owners/", views.admin_approved_bus_owners, name="admin_approved_bus_owners"),
path("approve-owner/<int:owner_id>/", views.approve_bus_owner, name="approve_bus_owner"),
path('complaint/<int:complaint_id>/', views.admin_complaint_detail, name='admin_complaint_detail'),
]
