from django.contrib import admin
from bus_owner.models import BusOwnerProfile
# Register your models here.
# admin.site.register(BusOwnerProfile)
# admin.site.register()

from django.contrib import admin
from .models import BusOwnerProfile, Route, Bus, BusSchedule
from django.contrib import admin
from .models import Route, BusSchedule, RouteStop


# 🧍 Bus Owner Profile Admin
@admin.register(BusOwnerProfile)
class BusOwnerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'contact_number', 'approved', 'registered_on')
    search_fields = ('user__username', 'contact_number')
    list_filter = ('approved',)



# 🛣️ Route Admin
@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('route_name', 'start_location', 'end_location', 'distance_km')
    search_fields = ('route_name', 'start_location', 'end_location')
    ordering = ('route_name',)


# 🚌 Bus Admin
@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ('bus_number', 'owner', 'total_seats', 'approved')
    list_filter = ('approved',)
    search_fields = ('bus_number', 'owner__company_name')
    ordering = ('bus_number',)


# 🕒 Bus Schedule Admin
@admin.register(BusSchedule)
class BusScheduleAdmin(admin.ModelAdmin):
    list_display = ('bus', 'route', 'departure_time', 'arrival_time', 'fare', 'active')
    list_filter = ('active', 'route', 'bus')
    search_fields = ('bus__bus_number', 'route__route_name')
    ordering = ('departure_time',)
    autocomplete_fields = ('bus', 'route')
