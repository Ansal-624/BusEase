from django.contrib import admin
from .models import BusOwnerProfile, Route, Bus, BusSchedule, RouteStop, Conductor, ConductorDuty


# 🧍 Bus Owner Profile Admin
@admin.register(BusOwnerProfile)
class BusOwnerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'contact_number', 'approved', 'registered_on')
    search_fields = ('user__username', 'contact_number')
    list_filter = ('approved',)
    readonly_fields = ('registered_on',)


# 🛣️ Route Admin
@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ('route_name', 'start_location', 'end_location', 'distance_km')
    search_fields = ('route_name', 'start_location', 'end_location')
    ordering = ('route_name',)


# 🚌 Bus Admin
@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = ('bus_number', 'bus_name', 'owner', 'total_seats', 'approved')
    list_filter = ('approved',)
    search_fields = ('bus_number', 'bus_name', 'owner__user__username')
    ordering = ('bus_number',)


# 🕒 Bus Schedule Admin
@admin.register(BusSchedule)
class BusScheduleAdmin(admin.ModelAdmin):
    list_display = ('bus', 'route', 'departure_time', 'arrival_time', 'fare', 'active')
    list_filter = ('active', 'route', 'bus')
    search_fields = ('bus__bus_number', 'route__route_name')
    ordering = ('departure_time',)
    autocomplete_fields = ('bus', 'route')


# 👨‍✈️ Conductor Admin
@admin.register(Conductor)
class ConductorAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'user', 'owner', 'phone', 'is_active', 'created_at')
    list_filter = ('is_active', 'owner')
    search_fields = ('employee_id', 'user__username', 'user__first_name', 'user__last_name', 'phone')
    readonly_fields = ('employee_id', 'created_at')
    autocomplete_fields = ('user', 'owner')
    
    fieldsets = (
        ('Personal Information', {
            'fields': ('user', 'employee_id', 'phone', 'address', 'profile_photo')
        }),
        ('Employment Details', {
            'fields': ('owner', 'is_active', 'created_at')
        }),
    )


# 🚍 Conductor Duty (Bus Assignment) Admin
@admin.register(ConductorDuty)
class ConductorDutyAdmin(admin.ModelAdmin):
    list_display = ('conductor', 'bus', 'assigned_at', 'is_active')
    list_filter = ('is_active', 'assigned_at')
    search_fields = ('conductor__user__username', 'conductor__employee_id', 'bus__bus_number')
    readonly_fields = ('assigned_at',)
    autocomplete_fields = ('conductor', 'bus', 'assigned_by')
    
    fieldsets = (
        ('Assignment Details', {
            'fields': ('conductor', 'bus', 'is_active')
        }),
        ('Assignment Metadata', {
            'fields': ('assigned_by', 'assigned_at')
        }),
    )


# 🚏 Route Stop Admin (if you want to register it)
@admin.register(RouteStop)
class RouteStopAdmin(admin.ModelAdmin):
    list_display = ('stop_name', 'route', 'order', 'arrival_time')
    list_filter = ('route',)
    search_fields = ('stop_name',)
    ordering = ('route', 'order')