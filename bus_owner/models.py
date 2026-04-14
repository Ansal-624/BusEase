from django.db import models
from django.conf import settings


# 🧍‍♂️ Bus Owner Profile
class BusOwnerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    contact_number = models.CharField(max_length=15)
    address = models.TextField()
    owner_photo = models.ImageField(upload_to='owner_photos/', null=True, blank=True)
    business_license = models.FileField(upload_to='business_licenses/', null=True, blank=True)
    id_proof = models.FileField(upload_to='owner_id_proofs/', null=True, blank=True)
    approved = models.BooleanField(default=False)
    registered_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Owner: {self.user.username}"


# 🛣️ Route Model




# 🚌 Bus Model
class Bus(models.Model):
    owner = models.ForeignKey(BusOwnerProfile, on_delete=models.CASCADE, related_name='buses')
    bus_name = models.CharField(max_length=100, default="Unnamed Bus")
    bus_number = models.CharField(max_length=20, unique=True)
    total_seats = models.PositiveIntegerField()
    owner_contact_number = models.CharField(max_length=15, blank=True, default="")
    driver_name = models.CharField(max_length=100, blank=True, default="")
    driver_contact_number = models.CharField(max_length=15, blank=True, default="")
    driver_license = models.FileField(upload_to='driver_licenses/', null=True, blank=True)
    registration_document = models.FileField(upload_to='registration_docs/', blank=True, null=True)
    pollution_test_certificate = models.FileField(upload_to='pollution_tests/', null=True, blank=True)
    insurance_document = models.FileField(upload_to='insurance_docs/', null=True, blank=True)
    approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.bus_name} ({self.bus_number})"

    class Meta:
        ordering = ['bus_number']
        verbose_name = "Bus"
        verbose_name_plural = "Buses"

class BusPhoto(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="bus_photos/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bus.bus_name} Photo"


## 🕒 Bus Schedule Model
class BusSchedule(models.Model):
    bus = models.ForeignKey('Bus', on_delete=models.CASCADE, related_name='schedules')
    route = models.ForeignKey('Route', on_delete=models.CASCADE, related_name='schedules')
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    fare = models.DecimalField(max_digits=8, decimal_places=2)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['departure_time']
        verbose_name = "Bus Schedule"
        verbose_name_plural = "Bus Schedules"

    def __str__(self):
        return (
            f"{self.bus.bus_number} | "
            f"{self.route.start_location} → {self.route.end_location} | "
            f"{self.departure_time.strftime('%Y-%m-%d %H:%M')}"
        )


# 1️⃣ Route
class Route(models.Model):
    route_name = models.CharField(max_length=200)
    start_location = models.CharField(max_length=100)
    end_location = models.CharField(max_length=100)
    route_path = models.JSONField(blank=True, null=True)
    distance_km = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.route_name


# 2️⃣ RouteStop
class RouteStop(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name='stops')
    stop_name = models.CharField(max_length=100)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    arrival_time = models.TimeField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.stop_name} ({self.route.route_name})"
    
    # Add this to bus_owner/models.py

from django.conf import settings

from django.conf import settings
from main.models import User  # Import your custom User model

# 👨‍✈️ Conductor Model
class Conductor(models.Model):
    """Model for bus conductors"""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conductor_profile'
    )
    owner = models.ForeignKey(
        'BusOwnerProfile',
        on_delete=models.CASCADE,
        related_name='conductors'
    )
    phone = models.CharField(max_length=15)
    address = models.TextField(blank=True)
    profile_photo = models.ImageField(upload_to='conductor_photos/', blank=True, null=True)
    employee_id = models.CharField(max_length=50, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.employee_id:
            import time
            self.employee_id = f"COND{int(time.time())}{self.user.id}"
        super().save(*args, **kwargs)
    
    @property
    def assigned_bus(self):
        """Get the bus assigned to this conductor"""
        try:
            # Use select_related to optimize and ensure fresh data
            duty = ConductorDuty.objects.select_related('bus').filter(
                conductor=self, 
                is_active=True
            ).first()
            return duty.bus if duty else None
        except Exception as e:
            print(f"Error getting assigned bus: {e}")
            return None
    
    def has_assigned_bus(self):
        """Check if conductor has an assigned bus"""
        return self.assigned_bus is not None
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} - {self.employee_id}"


# 📋 Conductor Duty Model (Permanent Assignment)
class ConductorDuty(models.Model):
    """Model for assigning conductors to buses (Permanent assignment)"""
    conductor = models.OneToOneField(
        'Conductor',
        on_delete=models.CASCADE,
        related_name='duty_assignment'  # Changed from 'assigned_bus' to avoid confusion
    )
    bus = models.ForeignKey(
        'Bus',
        on_delete=models.CASCADE,
        related_name='assigned_conductors'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='assigned_conductors'
    )
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['conductor', 'bus']
        ordering = ['-assigned_at']
    
    def __str__(self):
        return f"{self.conductor} → {self.bus.bus_number}"
    
class BusLiveLocation(models.Model):
    """Stores current live location of a bus (updated by conductor)"""
    
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name='live_locations')
    schedule = models.ForeignKey(BusSchedule, on_delete=models.CASCADE)
    current_stop = models.ForeignKey(RouteStop, on_delete=models.SET_NULL, null=True, blank=True)

    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    updated_by = models.ForeignKey('Conductor', on_delete=models.SET_NULL, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.bus.bus_number} - {self.current_stop}"