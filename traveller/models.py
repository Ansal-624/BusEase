from django.db import models
from django.conf import settings
from bus_owner.models import Bus, BusSchedule, RouteStop
from django.utils import timezone
from datetime import timedelta
from django.db import models
from django.conf import settings



class Booking(models.Model):
    traveller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookings"
    )
    bus = models.ForeignKey(
        Bus,
        on_delete=models.CASCADE,
        related_name="bookings"
    )
    schedule = models.ForeignKey(
        BusSchedule,
        on_delete=models.CASCADE,
        related_name="bookings",
        null=True,
        blank=True
    )
    seat_number = models.PositiveIntegerField()
    from_stop = models.ForeignKey(
        RouteStop,
        on_delete=models.CASCADE,
        related_name="bookings_from",
        null=True,
        blank=True
    )
    to_stop = models.ForeignKey(
        RouteStop,
        on_delete=models.CASCADE,
        related_name="bookings_to",
        null=True,
        blank=True
    )
    booking_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, default="Confirmed")

    # Fare field
    total_fare = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0
    )
    
    # Razorpay Payment Fields
    payment_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Razorpay payment ID"
    )
    payment_status = models.CharField(
        max_length=20, 
        default='Pending',
        choices=[
            ('Pending', 'Pending'),
            ('Paid', 'Paid'),
            ('Failed', 'Failed'),
            ('Refunded', 'Refunded')
        ]
    )
    payment_amount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        help_text="Amount paid"
    )
    payment_date = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True
    )
    razorpay_order_id = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Razorpay order ID"
    )
    
    # Additional fields for tracking
    payment_method = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Payment method used"
    )
    payment_response = models.TextField(
        blank=True,
        null=True,
        help_text="Full payment response from Razorpay"
    )

    class Meta:
        unique_together = ("schedule", "seat_number")
        ordering = ["-booking_date"]

    def __str__(self):
        return f"Booking {self.id} - {self.traveller.username} - Seat {self.seat_number} - {self.payment_status}"

# traveller/models.py



def default_valid_till():
    return timezone.now().date() + timedelta(days=180)


from django.db import models
from django.conf import settings
from django.utils import timezone

class ConcessionApplication(models.Model):
    traveller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    college_name = models.CharField(max_length=200)
    starting_location = models.CharField(max_length=100)
    ending_location = models.CharField(max_length=100)
    document = models.FileField(upload_to='concession_docs/')
    photo = models.ImageField(upload_to='concession_photos/', null=True, blank=False)

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Cancelled', 'Cancelled'),
        ('Expired', 'Expired'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')

    applied_on = models.DateTimeField(auto_now_add=True)
    approved_on = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    # 📝 Admin feedback reasons
    rejection_reason = models.TextField(null=True, blank=True)
    cancel_reason = models.TextField(null=True, blank=True)

    def is_expired(self):
        """Check if concession card has passed its expiry date."""
        return self.expiry_date and timezone.now().date() > self.expiry_date

    def auto_expire(self):
        """Automatically mark approved concessions as expired."""
        if self.status == 'Approved' and self.is_expired():
            self.status = 'Expired'
            self.save(update_fields=['status'])

    def __str__(self):
        return f"{self.traveller.username} - {self.status}"


class ECard(models.Model):
    traveller = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    card_id = models.CharField(max_length=20, unique=True)
    issued_on = models.DateTimeField(auto_now_add=True)
    valid_till = models.DateField()
    active = models.BooleanField(default=True)

    def deactivate(self):
        self.active = False
        self.save()

    def __str__(self):
        return f"E-Card {self.card_id} ({self.traveller.username})"




# Default validity: 6 months
def default_valid_till():
    return timezone.now().date() + timedelta(days=180)

from django.db import models
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from traveller.models import ConcessionApplication, ECard

# Default E-Card validity: 6 months
def default_valid_till():
    return timezone.now().date() + timedelta(days=180)


class ConcessionDetail(models.Model):
    traveller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='concession_details'
    )
    application = models.OneToOneField(
        'ConcessionApplication',
        on_delete=models.CASCADE,
        related_name='concession_detail'
    )
    ecard = models.OneToOneField(
        'ECard',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='concession_detail'
    )

    college_name = models.CharField(max_length=200)
    starting_location = models.CharField(max_length=100)
    ending_location = models.CharField(max_length=100)
    concession_percentage = models.PositiveIntegerField(default=50)

    valid_from = models.DateField(default=timezone.now)
    valid_till = models.DateField(default=default_valid_till)
    issued_on = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    cancelled_on = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(null=True, blank=True)

    def check_expiry(self):
        if self.active and self.valid_till < timezone.now().date():
            self.active = False
            self.save()
            self.application.status = "Expired"
            self.application.save()
            if self.ecard:
                self.ecard.deactivate()

    def cancel(self, reason=None):
        self.active = False
        self.cancelled_on = timezone.now()
        self.cancel_reason = reason
        self.save()
        self.application.status = "Cancelled"
        self.application.cancel_reason = reason
        self.application.save()
        if self.ecard:
            self.ecard.deactivate()

    def __str__(self):
        status = "Active" if self.active else "Inactive"
        return f"{self.traveller.username} - {self.concession_percentage}% ({status})"

    class Meta:
        verbose_name = "Concession Detail"
        verbose_name_plural = "Concession Details"
        ordering = ['-issued_on']
