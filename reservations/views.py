from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .forms import BookingForm, RoomForm
from .models import Room, Booking, Payment, PaymentType, RoomStatus, RoomType, RoomImage
from django.contrib.auth.decorators import login_required
from django.utils import timezone

#cognito
import hmac
import hashlib

from django.conf import settings
from django.shortcuts import redirect
from urllib.parse import quote
import base64
import requests
from jose import jwt
from django.http import HttpResponse

#DynamoDB
import uuid
import boto3
import json
from .forms import RoomForm
from decimal import Decimal
from datetime import datetime

#import roomsearch
from roomsearch.roomsearch.engine import RoomSearchEngine

def home(request):
    email = request.session.get("email")
    return render(request, "reservations/home.html", {"email": email})

client = boto3.client("cognito-idp", region_name=settings.COGNITO_REGION)

# -----------------------------
# USER LOGIN (username + password)
# -----------------------------
def login(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            resp = client.initiate_auth(
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={
                    "USERNAME": email,
                    "PASSWORD": password,
                    "SECRET_HASH": get_secret_hash(email),
                },
                ClientId=settings.COGNITO_CLIENT_ID
            )

            result = resp["AuthenticationResult"]

            request.session["id_token"] = result["IdToken"]
            request.session["access_token"] = result["AccessToken"]
            request.session["email"] = email

            return redirect("home")

        except client.exceptions.NotAuthorizedException:
            return HttpResponse("Invalid username or password")
        except Exception as e:
            return HttpResponse(str(e))

    return render(request, "reservations/login.html")


# -----------------------------
# LOGOUT
# -----------------------------
def logout(request):
    request.session.flush()
    return redirect("home")


# -----------------------------
# SIGNUP
# -----------------------------
def get_secret_hash(username):
    message = username + settings.COGNITO_CLIENT_ID
    dig = hmac.new(
        settings.COGNITO_CLIENT_SECRET.encode("utf-8"),
        msg=message.encode("utf-8"),
        digestmod=hashlib.sha256
    ).digest()
    return base64.b64encode(dig).decode()

def signup(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            client.sign_up(
                ClientId=settings.COGNITO_CLIENT_ID,
                SecretHash=get_secret_hash(email),
                Username=email,
                Password=password,
                UserAttributes=[
                    {"Name": "email", "Value": email}
                ]
            )
            request.session["pending_email"] = email
            return redirect("verify")
            
        except Exception as e:
            return HttpResponse(str(e))

    return render(request, "reservations/signup.html")

def verify(request):
    email = request.session.get("pending_email")

    if not email:
        return HttpResponse("No pending email found in session.", status=400)
        
    if request.method == "POST":
        code = request.POST.get("code")

        if not code:
            return HttpResponse("Verification code is required.", status=400)

        try:
            client.confirm_sign_up(
                ClientId=settings.COGNITO_CLIENT_ID,
                Username=email,
                ConfirmationCode=code,
                SecretHash=get_secret_hash(email)
            )
            del request.session["pending_email"]
            return redirect("login")
            
        except Exception as e:
            return HttpResponse(str(e), status=400)
            
    return render(request, "reservations/verify.html")

    
# def login_redirect(request):
#     cognito_url = (
#         f"https://{settings.COGNITO_DOMAIN}/oauth2/authorize?"
#         f"client_id={settings.COGNITO_CLIENT_ID}"
#         f"&response_type=code"
#         f"&scope=email+openid+profile"
#         f"&redirect_uri={settings.COGNITO_REDIRECT_URI}"
#     )
#     return redirect(cognito_url)


# def callback(request):
#     code = request.GET.get("code")
#     if not code:
#         return HttpResponse("No code returned", status=400)

#     # Token endpoint
#     token_url = f"https://{settings.COGNITO_DOMAIN}/oauth2/token"

#     # Client secret in Basic Auth header
#     auth_str = f"{settings.COGNITO_CLIENT_ID}:{settings.COGNITO_CLIENT_SECRET}"
#     b64_auth_str = base64.b64encode(auth_str.encode()).decode()
#     headers = {
#         "Content-Type": "application/x-www-form-urlencoded",
#         "Authorization": f"Basic {b64_auth_str}"
#     }

#     data = {
#         "grant_type": "authorization_code",
#         "code": code,
#         "redirect_uri": settings.COGNITO_REDIRECT_URI
#     }

#     resp = requests.post(token_url, data=data, headers=headers)
#     tokens = resp.json()

#     if "id_token" not in tokens:
#         return HttpResponse(f"Error fetching tokens: {tokens}", status=400)

#     # Here you can decode the JWT to get user info
#     id_token = tokens["id_token"]
    
#     decoded = jwt.get_unverified_claims(id_token)
#     email = decoded.get("email")

#     # OPTIONAL: store in session
#     request.session["id_token"] = id_token
#     request.session["email"] = email
    
#     request.session.modified = True

#     return redirect("home")

# def logout_view(request):
#     # Clear Django session completely
#     request.session.flush()

#     # Build Cognito logout URL
#     logout_url = (
#         f"https://{settings.COGNITO_DOMAIN}/logout"
#         f"?client_id={settings.COGNITO_CLIENT_ID}"
#         f"&logout_uri={settings.COGNITO_LOGOUT_URL}"
#     )

#     # After clearing session/cookies, redirect user to Cognito logout
#     # Cognito will then redirect back to your logout_uri
#     return redirect(logout_url)
    
dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
table = dynamodb.Table(settings.AWS_DYNAMODB_TABLE)
s3 = boto3.client("s3")

def create_room(request):
    if request.method == "POST":
        form = RoomForm(request.POST, request.FILES)
        if form.is_valid():
            room_id = str(uuid.uuid4())
            
            image = request.FILES.get("image")
            
            image_key = None
            
            if image :
                
                image_key = f"rooms/{room_id}/{image.name}"
                
                # Upload to S3 (IAM role used automatically)
                s3.upload_fileobj(
                    image,
                    settings.AWS_S3_BUCKET_NAME,
                    image_key,
                    ExtraArgs={"ContentType": image.content_type}
                )
            
            table.put_item(
                Item={
                    "roomId": room_id,
                    "occupancy": form.cleaned_data["occupancy"],
                    "bed_size": form.cleaned_data["bed_size"],
                    "layout": form.cleaned_data["layout"],
                    "wifi": form.cleaned_data["wifi"],
                    "price": str(form.cleaned_data["price"]),
                    "rating": str(form.cleaned_data["rating"]),
                    "description": form.cleaned_data["description"],
                    "image_key": image_key,
                }
            )

            return render(request, "reservations/home.html", {"room_id": room_id})
    else:
        form = RoomForm()

    return render(request, "reservations/add_room_type.html", {"form": form})
    
bookings_table = dynamodb.Table(settings.AWS_DYNAMODB_TABLE_1)

def list_rooms(request):
    response = table.scan()  # get all rows
    rooms = response.get("Items", [])

    # Convert Decimal to float for template
    for room in rooms:
        for key, value in room.items():
            if isinstance(value, Decimal):
                room[key] = float(value)
        # Generate pre-signed image URL if image_key exists
        image_key = room.get("image_key")
        if image_key:
            room["image_url"] = s3.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.AWS_S3_BUCKET_NAME,
                    "Key": image_key
                },
                ExpiresIn=3600  # 1 hour
            )
        else:
            room["image_url"] = None
    
        booking = bookings_table.query(
            IndexName="roomId-index",   # you MUST create this GSI
            KeyConditionExpression=boto3.dynamodb.conditions.Key('roomId').eq(room["roomId"]),
            ScanIndexForward=False,
            Limit=1
        ).get("Items", [])

        if booking:
            room["payment_status"] = booking[0]["payment_status"]
        else:
            room["payment_status"] = "AVAILABLE"

    return render(request, "reservations/list_room_types.html", {"rooms": rooms})
    
def book_room(request, room_id):
    if request.method == "POST":

        start_date = request.POST["start_date"]
        end_date = request.POST["end_date"]

        payload = {
            "roomId": room_id,
            "start_date": start_date,
            "end_date": end_date,
        }

        response = requests.post(settings.API_GATEWAY_BOOK_URL, json=payload)

        raw = response.text  # always string
        print("RAW RESPONSE:", raw)

        try:
            outer = response.json()
        except:
            outer = {}

        # Determine if "outer" has "body"
        if isinstance(outer, dict) and "body" in outer:
            # AWS REST API returns {"body": "json-string"}
            inner = json.loads(outer["body"])
        else:
            # Direct body JSON string
            inner = json.loads(raw)

        print("PARSED INNER:", inner)

        booking_id = inner.get("bookingId")
        total_price = inner.get("total_price")
        number_of_days = inner.get("number_of_days")
        
        if not booking_id:
            return HttpResponse("Booking failed: " + str(inner))

        # Redirect to dummy payment page
        return redirect(f"/payment/{booking_id}/{total_price}")

    return render(request, "reservations/book_room.html", {"room_id": room_id})
 
def payment(request, booking_id, total_price):
    API_GATEWAY_PAYMENT_URL = settings.API_GATEWAY_PAYMENT_URL
    SNS_TOPIC_ARN = settings.SNS_TOPIC_ARN
    if request.method == "POST":
        payload = {"bookingId": booking_id}

        response = requests.post(API_GATEWAY_PAYMENT_URL, json=payload)

        raw = response.text
        print("RAW PAYMENT RESPONSE:", raw)

        try:
            outer = response.json()
        except:
            outer = {}

        # Parse inner "body"
        if isinstance(outer, dict) and "body" in outer:
            inner = json.loads(outer["body"])
        else:
            inner = json.loads(raw)

        status = inner.get("status")
        
         # SNS without adding permissions
        sns = boto3.client("sns", region_name="us-east-1")

        message = (
            f"Hello {request.user.username},\n\n"
            f"Your payment was successful!\n"
            f"Booking ID: {booking_id}\n"
            f"Total Paid: ${total_price}\n"
            f"Status: {status}\n\n"
            f"Thank you for booking with us."
        )

        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="Payment Confirmation",
            Message=message
        )

        return render(request, "reservations/payment_success.html", {"status": status})

    return render(request, "reservations/payment.html", {"booking_id": booking_id, "total_price": total_price})



def payment_success(request):
    return render(request, "payment_success.html")


def room_search(request):
    # Search Library API
    search_engine = RoomSearchEngine()

    filters = {
        "occupancy": request.GET.get("occupancy", "").strip(),
        "bed_size": request.GET.get("bed_size", "").strip(),
        "layout": request.GET.get("layout", "").strip(),
        "wifi": request.GET.get("wifi", "").strip(),
        "min_price": request.GET.get("min_price", "").strip(),
        "max_price": request.GET.get("max_price", "").strip(),
        "rating": request.GET.get("rating", "").strip(),
        "keyword": request.GET.get("keyword", "").strip(),
    }

    #results = search(filters)
    results = search_engine.search(filters)
    
    for room in results:
        image_key = room.get("image_key")
        if image_key:
            room["image_url"] = s3.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.AWS_S3_BUCKET_NAME,
                    "Key": image_key
                },
                ExpiresIn=3600  # 1 hour
            )
        else:
            room["image_url"] = None
            
    return render(request, "reservations/room_search.html", {
        "results": results,
        "filters": filters
    })







# @login_required
# def room_detail(request, room_id):
#     room = Room.objects.get(id=room_id)
#     return render(request, 'reservations/room_detail.html', {'room': room})

# # @login_required
# # def book_room(request, user_id):
# #     room = get_object_or_404(Room, pk=pk)
# #     # simple check: must be 'available' status to book
# #     if room.room_status.status.lower() != 'available':
# #         messages.error(request, "Room not available")
# #         return redirect('room_detail', pk=pk)

# #     if request.method == 'POST':
# #         form = BookingForm(request.POST)
# #         if form.is_valid():
# #             booking = form.save(commit=False)
# #             booking.customer = request.user
# #             # assign a staff (first receptionist) - in real app pick by availability
# #             receptionist = Receptionist.objects.first()
# #             booking.staff = receptionist
# #             booking.payment = None  # payment created after confirmation
# #             booking.save()
# #             messages.success(request, f'Booking created: {booking.id}')
# #             return redirect('booking_detail', pk=booking.id)
# #     else:
# #         form = BookingForm(initial={'room': room})
# #     return render(request, 'reservations/book_room.html', {'form': form, 'room': room})

# @login_required
# def booking_detail(request, pk):
#     booking = get_object_or_404(Booking, pk=pk, customer=request.user)
#     return render(request, 'reservations/booking_detail.html', {'booking': booking})

# # Payment stub: create payment record (no external gateway)
# @login_required
# def pay_booking(request, booking_id):
#     booking = get_object_or_404(Booking, pk=booking_id, customer=request.user)
#     if request.method == 'POST':
#         # pick default payment type or create one
#         ptype, _ = PaymentType.objects.get_or_create(name='Card')
#         receptionist = booking.staff
#         amount = booking.room.price
#         payment = Payment.objects.create(payment_type=ptype, customer=request.user, staff=receptionist, amount=amount)
#         booking.payment = payment
#         booking.save()
#         # update room status to 'booked'
#         booked_status, _ = RoomStatus.objects.get_or_create(status='Booked')
#         booking.room.room_status = booked_status
#         booking.room.save()
#         messages.success(request, 'Payment successful and booking confirmed.')
#         return redirect('booking_detail', pk=booking.id)
#     return render(request, 'reservations/pay_booking.html', {'booking': booking})

# @login_required
# def add_room_type(request, room_type_id=None):
#     """Allow staff or admin to create a new room type"""
#     if room_type_id:
#         room_type = get_object_or_404(RoomType, id=room_type_id)
#         action = "Edit"
#     else:
#         room_type = None
#         action = "Add"
        
#     if request.method == 'POST':
#         # Delete the entire room type
#         if request.POST.get('action') == 'delete' and room_type:
#             print(request.POST.dict())
#             room_type.delete()
#             messages.success(request, "Room type deleted successfully.")
#             return redirect('list_room_types')

#         # Delete a single image
#         delete_image_id = request.POST.get('delete_image_id')
#         if delete_image_id:
#             image = get_object_or_404(RoomImage, id=delete_image_id)
#             image.delete()
#             messages.success(request, "Image deleted successfully.")
#             return redirect('edit_room_type', room_type_id=room_type.id)
        
#         # Add/Edit room type
#         form = RoomTypeForm(request.POST, instance=room_type)
#         if form.is_valid():
#             room_type = form.save()
#             images = request.FILES.getlist('images')
#             for image in images:
#                 RoomImage.objects.create(room_type=room_type, image=image)
#             return redirect('list_room_types')
#     else:
#         form = RoomTypeForm(instance=room_type)
    
#     images = room_type.images.all() if room_type else []
#     return render(request, 'reservations/add_room_type.html', {
#         'form': form,
#         'action': action,
#         'room_type': room_type,
#         'images': images,
#     })

# def list_room_types(request):
#     """List all room types"""
#     room_types = RoomType.objects.prefetch_related('images').all()
#     return render(request, 'reservations/list_room_types.html', {'room_types': room_types})

# def edit_room_type(request, room_type_id):
#     """Edit existing room type and add new images"""
#     room_type = get_object_or_404(RoomType, id=room_type_id)

#     if request.method == 'POST':
#         form = RoomTypeForm(request.POST, instance=room_type)
#         files = request.FILES.getlist('images')
#         if form.is_valid():
#             form.save()
#             # Add new images if uploaded
#             for file in files:
#                 RoomImage.objects.create(room_type=room_type, image=file)
#             return redirect('list_room_types')
#     else:
#         form = RoomTypeForm(instance=room_type)

#     images = room_type.images.all()
#     return render(request, 'reservations/edit_room_type.html', {
#         'form': form,
#         'room_type': room_type,
#         'images': images
#     })
