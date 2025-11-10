from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Receptionist, RoomType, RoomStatus, Room, PaymentType, Payment, Booking

class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'phone_number', 'is_admin', 'is_superadmin')
    search_fields = ('username', 'email', 'phone_number')
    ordering = ('username',)
    fieldsets = (
        (None, {'fields': ('username', 'email', 'phone_number', 'password')}),
        ('Permissions', {'fields': ('is_admin', 'is_superadmin', 'is_staff', 'is_superuser')}),
        ('Status', {'fields': ('email_verified', 'otp_code')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'phone_number', 'password1', 'password2'),
        }),
    )

admin.site.register(User, CustomUserAdmin)
admin.site.register(Receptionist)
admin.site.register(RoomType)
admin.site.register(RoomStatus)
admin.site.register(Room)
admin.site.register(PaymentType)
admin.site.register(Payment)
admin.site.register(Booking)
