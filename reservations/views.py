from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import BookingForm, RoomTypeForm
from .models import Room, Booking, Payment, PaymentType, RoomStatus, RoomType, RoomImage
from django.contrib.auth.decorators import login_required
from django.utils import timezone

from django.conf import settings
from django.shortcuts import redirect
from urllib.parse import quote
import base64
import requests
from jose import jwt
from django.http import HttpResponse

def home(request):
    email = request.session.get("email")
    return render(request, "reservations/home.html", {"email": email})
    
def login_redirect(request):
    cognito_url = (
        f"https://{settings.COGNITO_DOMAIN}/oauth2/authorize?"
        f"client_id={settings.COGNITO_CLIENT_ID}"
        f"&response_type=code"
        f"&scope=email+openid+profile"
        f"&redirect_uri={settings.COGNITO_REDIRECT_URI}"
    )
    return redirect(cognito_url)


def callback(request):
    code = request.GET.get("code")
    if not code:
        return HttpResponse("No code returned", status=400)

    # Token endpoint
    token_url = f"https://{settings.COGNITO_DOMAIN}/oauth2/token"

    # Client secret in Basic Auth header
    auth_str = f"{settings.COGNITO_CLIENT_ID}:{settings.COGNITO_CLIENT_SECRET}"
    b64_auth_str = base64.b64encode(auth_str.encode()).decode()
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {b64_auth_str}"
    }

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.COGNITO_REDIRECT_URI
    }

    resp = requests.post(token_url, data=data, headers=headers)
    tokens = resp.json()

    if "id_token" not in tokens:
        return HttpResponse(f"Error fetching tokens: {tokens}", status=400)

    # Here you can decode the JWT to get user info
    id_token = tokens["id_token"]
    
    decoded = jwt.get_unverified_claims(id_token)
    email = decoded.get("email")

    # OPTIONAL: store in session
    request.session["id_token"] = id_token
    request.session["email"] = email
    
    request.session.modified = True

    return redirect("home")

def logout_view(request):
    # Clear Django session completely
    request.session.flush()

    # Build Cognito logout URL
    logout_url = (
        f"https://{settings.COGNITO_DOMAIN}/logout"
        f"?client_id={settings.COGNITO_CLIENT_ID}"
        f"&logout_uri={settings.COGNITO_LOGOUT_URL}"
    )

    # After clearing session/cookies, redirect user to Cognito logout
    # Cognito will then redirect back to your logout_uri
    return redirect(logout_url)
    
@login_required
def room_detail(request, room_id):
    room = Room.objects.get(id=room_id)
    return render(request, 'reservations/room_detail.html', {'room': room})

@login_required
def book_room(request, user_id):
    room = get_object_or_404(Room, pk=pk)
    # simple check: must be 'available' status to book
    if room.room_status.status.lower() != 'available':
        messages.error(request, "Room not available")
        return redirect('room_detail', pk=pk)

    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.customer = request.user
            # assign a staff (first receptionist) - in real app pick by availability
            receptionist = Receptionist.objects.first()
            booking.staff = receptionist
            booking.payment = None  # payment created after confirmation
            booking.save()
            messages.success(request, f'Booking created: {booking.id}')
            return redirect('booking_detail', pk=booking.id)
    else:
        form = BookingForm(initial={'room': room})
    return render(request, 'reservations/book_room.html', {'form': form, 'room': room})

@login_required
def booking_detail(request, pk):
    booking = get_object_or_404(Booking, pk=pk, customer=request.user)
    return render(request, 'reservations/booking_detail.html', {'booking': booking})

# Payment stub: create payment record (no external gateway)
@login_required
def pay_booking(request, booking_id):
    booking = get_object_or_404(Booking, pk=booking_id, customer=request.user)
    if request.method == 'POST':
        # pick default payment type or create one
        ptype, _ = PaymentType.objects.get_or_create(name='Card')
        receptionist = booking.staff
        amount = booking.room.price
        payment = Payment.objects.create(payment_type=ptype, customer=request.user, staff=receptionist, amount=amount)
        booking.payment = payment
        booking.save()
        # update room status to 'booked'
        booked_status, _ = RoomStatus.objects.get_or_create(status='Booked')
        booking.room.room_status = booked_status
        booking.room.save()
        messages.success(request, 'Payment successful and booking confirmed.')
        return redirect('booking_detail', pk=booking.id)
    return render(request, 'reservations/pay_booking.html', {'booking': booking})

@login_required
def add_room_type(request, room_type_id=None):
    """Allow staff or admin to create a new room type"""
    if room_type_id:
        room_type = get_object_or_404(RoomType, id=room_type_id)
        action = "Edit"
    else:
        room_type = None
        action = "Add"
        
    if request.method == 'POST':
        # Delete the entire room type
        if request.POST.get('action') == 'delete' and room_type:
            print(request.POST.dict())
            room_type.delete()
            messages.success(request, "Room type deleted successfully.")
            return redirect('list_room_types')

        # Delete a single image
        delete_image_id = request.POST.get('delete_image_id')
        if delete_image_id:
            image = get_object_or_404(RoomImage, id=delete_image_id)
            image.delete()
            messages.success(request, "Image deleted successfully.")
            return redirect('edit_room_type', room_type_id=room_type.id)
        
        # Add/Edit room type
        form = RoomTypeForm(request.POST, instance=room_type)
        if form.is_valid():
            room_type = form.save()
            images = request.FILES.getlist('images')
            for image in images:
                RoomImage.objects.create(room_type=room_type, image=image)
            return redirect('list_room_types')
    else:
        form = RoomTypeForm(instance=room_type)
    
    images = room_type.images.all() if room_type else []
    return render(request, 'reservations/add_room_type.html', {
        'form': form,
        'action': action,
        'room_type': room_type,
        'images': images,
    })

def list_room_types(request):
    """List all room types"""
    room_types = RoomType.objects.prefetch_related('images').all()
    return render(request, 'reservations/list_room_types.html', {'room_types': room_types})

def edit_room_type(request, room_type_id):
    """Edit existing room type and add new images"""
    room_type = get_object_or_404(RoomType, id=room_type_id)

    if request.method == 'POST':
        form = RoomTypeForm(request.POST, instance=room_type)
        files = request.FILES.getlist('images')
        if form.is_valid():
            form.save()
            # Add new images if uploaded
            for file in files:
                RoomImage.objects.create(room_type=room_type, image=file)
            return redirect('list_room_types')
    else:
        form = RoomTypeForm(instance=room_type)

    images = room_type.images.all()
    return render(request, 'reservations/edit_room_type.html', {
        'form': form,
        'room_type': room_type,
        'images': images
    })
