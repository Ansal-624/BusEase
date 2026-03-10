from django.db import models

# Create your models here.
from django.db import models
from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


from django.db import models
from django.conf import settings

class Complaint(models.Model):

    STATUS_CHOICES = [
        ("Pending", "Pending"),
        ("Checking", "Checking"),
        ("Action", "We will take action"),
        ("Invalid", "Invalid complaint"),
    ]

    traveller = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    attachment = models.FileField(upload_to="complaints/", blank=True, null=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Pending")
    admin_note = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.subject
