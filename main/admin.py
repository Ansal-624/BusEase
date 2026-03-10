from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User




class CustomUserAdmin(UserAdmin):
    model = User

    list_display = ('username', 'email', 'role', 'is_staff', 'is_superuser', 'is_active')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('email',)}),
        ('Roles and Permissions', {
            'fields': (
                'role',
                'is_staff',
                'is_active',
                'is_superuser',
                'groups',
                'user_permissions',
            )
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username',
                'email',
                'role',
                'password1',
                'password2',
                'is_staff',
                'is_active'
            ),
        }),
    )

    search_fields = ('username', 'email')
    ordering = ('username',)

    # ✅ Automatically set role to "admin" for superusers
    def save_model(self, request, obj, form, change):
        if obj.is_superuser:
            obj.role = 'admin'
        obj.save()


# ✅ Register Custom Admin
admin.site.register(User, CustomUserAdmin)


# admin.site.register(Notification)

# from django.contrib import admin
# from .models import Notification

# @admin.register(Notification)
# class NotificationAdmin(admin.ModelAdmin):
#     list_display = ('id', 'subject', 'sender', 'recipient', 'type', 'read', 'created_at')
#     list_filter = ('type', 'read', 'created_at')
#     search_fields = ('subject', 'body', 'sender__username', 'recipient__username')
#     ordering = ('-created_at',)
