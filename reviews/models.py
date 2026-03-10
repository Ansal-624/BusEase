

# Create your models here.
from django.conf import settings
from django.db import models
from bus_owner.models import Bus

User = settings.AUTH_USER_MODEL


class AppReview(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField(default=5)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.rating}★"


class BusReview(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name="reviews")
    traveller = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.bus.bus_name} - {self.rating}★"
