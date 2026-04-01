# reservations/models.py
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
import logging

class User(AbstractUser):
    pass

# RoomType
class RoomType(models.Model):
    occupancy = models.CharField(max_length=20, blank=True, null=True)
    bed_size = models.CharField(max_length=20, blank=True, null=True)
    layout = models.CharField(max_length=20, blank=True, null=True)
    wifi = models.BooleanField(default=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    rating = models.PositiveSmallIntegerField(default=3)
    description = models.TextField(blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f"{self.layout} - {self.bed_size} - {self.occupancy}"

# RoomStatus
class RoomStatus(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f'Room {self.status}'

# Room
class Room(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, related_name='rooms')
    room_status = models.ForeignKey(RoomStatus, on_delete=models.CASCADE, related_name='rooms')
    room_no = models.CharField(max_length=5, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f'Room {self.room_no} price:{self.price} is currently {self.room_status.status}'

# PaymentType
class PaymentType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=30, unique=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f'Payment option {self.name}'

# Payment
class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment_type = models.ForeignKey(PaymentType, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f'Customer {self.customer} amount:{self.amount} processed by staff {self.staff}'

# Booking
class Booking(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, null=True, blank=True)
    check_in = models.DateField(null=True, blank=True)
    check_out = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f'Booking by customer {self.customer} paid {self.payment} for room {self.room}'
        

logger = logging.getLogger(__name__)

@receiver(post_save,   sender=Booking)
@receiver(post_delete, sender=Booking)
def booking_changed(sender, instance, **kwargs):
    """Trigger Glue job whenever a Booking is saved or deleted."""
    COOLDOWN_KEY     = "glue_job_cooldown"
    COOLDOWN_SECONDS = 120

    if cache.get(COOLDOWN_KEY):
        logger.info("Glue trigger skipped — cooldown active")
        return

    try:
        from .spark_report import trigger_glue_job
        run_id = trigger_glue_job()
        cache.set(COOLDOWN_KEY, True, COOLDOWN_SECONDS)
        logger.info(f"Glue job triggered on Booking change. Run ID: {run_id}")
    except Exception as e:
        logger.error(f"Glue auto-trigger failed: {e}")