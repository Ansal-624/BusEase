from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Complaint


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("subject", "traveller", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("subject", "description", "traveller__username")
