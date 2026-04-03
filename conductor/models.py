from django.db import models

# Create your models here.


from django.db import models
from django.conf import settings
from bus_owner.models import Conductor, Bus, BusSchedule, RouteStop

class ConductorSeatUpdate(models.Model):
    """Model to track seat status updates by conductor"""
    STATUS_CHOICES = [
        ('booked', 'Booked'),
        ('occupied', 'Occupied'),
        ('cancelled', 'Cancelled'),
        ('empty', 'Empty'),
    ]
    
    conductor = models.ForeignKey(
        Conductor,
        on_delete=models.CASCADE,
        related_name='seat_updates'
    )
    bus = models.ForeignKey(
        Bus,
        on_delete=models.CASCADE,
        related_name='conductor_seat_updates'
    )
    schedule = models.ForeignKey(
        BusSchedule,
        on_delete=models.CASCADE,
        related_name='conductor_seat_updates'
    )
    seat_number = models.PositiveIntegerField()
    from_stop = models.ForeignKey(
        RouteStop,
        on_delete=models.CASCADE,
        related_name='conductor_from_updates',
        null=True,
        blank=True
    )
    to_stop = models.ForeignKey(
        RouteStop,
        on_delete=models.CASCADE,
        related_name='conductor_to_updates',
        null=True,
        blank=True
    )
    passenger_name = models.CharField(max_length=100, blank=True)
    passenger_phone = models.CharField(max_length=15, blank=True)
    fare_collected = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='booked')
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Seat {self.seat_number} on {self.bus.bus_number} - {self.status}"