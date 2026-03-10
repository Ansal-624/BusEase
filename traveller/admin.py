from django.contrib import admin
from django.utils import timezone
from datetime import timedelta
from django.utils.html import format_html
from .models import Booking, ConcessionApplication, ECard, ConcessionDetail


# 🎟️ Booking Admin
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('traveller', 'bus', 'seat_number', 'status', 'booking_date')
    list_filter = ('status', 'booking_date')
    search_fields = ('traveller__username', 'bus__bus_number')
    ordering = ('-booking_date',)
    list_per_page = 20


# 🧾 Concession Application Admin (Enhanced with expiry + cancel options)
@admin.register(ConcessionApplication)
class ConcessionApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'traveller', 'college_name',
        'starting_location', 'ending_location',
        'status', 'applied_on', 'approved_on', 'expiry_date',
        'cancel_reason_display'
    )
    list_filter = ('status', 'applied_on')
    search_fields = ('traveller__username', 'college_name')
    ordering = ('-applied_on',)
    list_per_page = 20
    list_editable = ('status',)
    actions = ['approve_with_expiry', 'cancel_ecard']

    def document_link(self, obj):
        if obj.document:
            return format_html("<a href='{}' target='_blank'>View Document</a>", obj.document.url)
        return "No Document"
    document_link.short_description = "Document"

    def cancel_reason_display(self, obj):
        return obj.cancel_reason or "—"
    cancel_reason_display.short_description = "Cancel Reason"

    # ✅ Approve applications and issue E-Card with expiry date
    def approve_with_expiry(self, request, queryset):
        from .models import ConcessionDetail  # avoid circular import
        for app in queryset.filter(status='Pending'):
            expiry_date = timezone.now().date() + timedelta(days=180)
            app.status = 'Approved'
            app.approved_on = timezone.now()
            app.expiry_date = expiry_date
            app.save()

            ecard = ECard.objects.create(
                traveller=app.traveller,
                card_id=f"EC{app.id:04}",
                valid_till=expiry_date,
            )

            ConcessionDetail.objects.create(
                traveller=app.traveller,
                application=app,
                ecard=ecard,
                college_name=app.college_name,
                starting_location=app.starting_location,
                ending_location=app.ending_location,
                valid_till=expiry_date,
            )
        self.message_user(request, "✅ Selected applications approved and E-Cards issued.")
    approve_with_expiry.short_description = "Approve + Issue E-Card (auto expiry)"

    # ❌ Cancel selected E-Cards with reason
    def cancel_ecard(self, request, queryset):
        for app in queryset.filter(status='Approved'):
            app.status = 'Cancelled'
            app.cancel_reason = "Cancelled by admin"
            app.save()

            # Deactivate E-Card and Concession detail if exist
            if hasattr(app, 'concession_detail'):
                detail = app.concession_detail
                if detail.ecard:
                    detail.ecard.active = False
                    detail.ecard.save()
                detail.active = False
                detail.save()
        self.message_user(request, "❌ Selected E-Cards have been cancelled.")
    cancel_ecard.short_description = "Cancel selected E-Cards"


# 💳 ECard Admin (with active control)
@admin.register(ECard)
class ECardAdmin(admin.ModelAdmin):
    list_display = ('card_id', 'traveller', 'issued_on', 'valid_till', 'active_status')
    search_fields = ('card_id', 'traveller__username')
    ordering = ('-issued_on',)
    list_per_page = 20
    actions = ['deactivate_selected']

    def active_status(self, obj):
        color = "green" if obj.active else "red"
        return format_html(f"<b style='color:{color}'>{'Active' if obj.active else 'Inactive'}</b>")
    active_status.short_description = "Status"

    def deactivate_selected(self, request, queryset):
        queryset.update(active=False)
        self.message_user(request, "🟥 Selected E-Cards deactivated.")
    deactivate_selected.short_description = "Deactivate selected E-Cards"


# 📘 Concession Detail Admin (for record tracking)
@admin.register(ConcessionDetail)
class ConcessionDetailAdmin(admin.ModelAdmin):
    list_display = ('traveller', 'college_name', 'valid_from', 'valid_till', 'active')
    list_filter = ('active',)
    search_fields = ('traveller__username', 'college_name')
    ordering = ('-issued_on',)
