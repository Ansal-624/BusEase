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
urlpatterns = [
    # path('register-extra/', views.owner_register_extra, name='owner_register_extra'),
    path('register/', views.owner_register, name='owner_register'),
    path('add-bus/', views.add_bus, name='add_bus'), 
    path('dashboard/', views.owner_dashboard, name='owner_dashboard'),
    path('buses/', views.view_buses, name='view_buses'),
    path('buses/status/', views.bus_status, name='bus_status'),   
    path('add_schedule/<int:bus_id>/', views.add_schedule, name='add_schedule'),
    path('delete_bus/<int:bus_id>/', views.delete_bus, name='delete_bus'),
    path('delete_schedule/<int:schedule_id>/', views.delete_schedule, name='delete_schedule'),
    path('bookings/<int:bus_id>/', views.view_bookings, name='view_bookings'),
    path('bus-details/<int:bus_id>/', views.bus_details, name='bus_details'),
    path('buses/', views.view_buses, name='view_buses'),
    # path('bus/<int:bus_id>/', views.bus_detail, name='bus_detail'),
    # path('bus/<int:bus_id>/schedules/', views.bus_schedules, name='bus_schedules'),
    path('bus-schedules/', views.bus_schedules, name='bus_schedules'),
    path('conductors/', views.owner_conductors_list, name='owner_conductors_list'),
path('conductors/add/', views.owner_add_conductor, name='owner_add_conductor'),
path('conductors/edit/<int:conductor_id>/', views.owner_edit_conductor, name='owner_edit_conductor'),
path('conductors/delete/<int:conductor_id>/', views.owner_delete_conductor, name='owner_delete_conductor'),

# Duty Assignment
path('duties/', views.owner_duty_assignments, name='owner_duty_assignments'),
path('duties/assign/', views.owner_assign_duty, name='owner_assign_duty'),
path('duties/cancel/<int:duty_id>/', views.owner_cancel_duty, name='owner_cancel_duty'),
path('conductor/unassign/<int:conductor_id>/', views.owner_unassign_conductor, name='owner_unassign_conductor'),


 

     
]
