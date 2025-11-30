from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import BookingForm, RoomForm
from .models import Room, Booking, Payment, RoomStatus, RoomType
from .decorators import cognito_email_allowed, unauthenticated_user

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

#Library API
import roomsearch

client = boto3.client("cognito-idp", region_name=settings.COGNITO_REGION)
sns = boto3.client("sns", region_name="us-east-1")

def home(request):
    email = request.session.get("email")
    return render(request, "reservations/home.html", {"email": email})

def amenities_page(request):
    email = request.session.get("email")
    return render(request, 'reservations/amenities.html', {"email": email})

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

def logout(request):
    request.session.flush()
    return redirect("home")

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
            
            # Subscribe user to SNS topic
            sns.subscribe(
                TopicArn=settings.SNS_TOPIC_ARN,
                Protocol="email",
                Endpoint=email
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

dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
table = dynamodb.Table(settings.AWS_DYNAMODB_TABLE)
s3 = boto3.client("s3")

@cognito_email_allowed(['vishalv1705@gmail.com'])
def create_room(request):
    email = request.session.get("email")
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

            return render(request, "reservations/home.html", {"room_id": room_id, "email": email})
    else:
        form = RoomForm()

    return render(request, "reservations/add_room_type.html", {"form": form, "email": email})
    
bookings_table = dynamodb.Table(settings.AWS_DYNAMODB_TABLE_1)

def list_rooms(request):
    email = request.session.get("email")
    response = table.scan()  
    rooms = response.get("Items", [])

    for room in rooms:
        for key, value in room.items():
            if isinstance(value, Decimal):
                room[key] = float(value)
        
        image_key = room.get("image_key")
        if image_key:
            room["image_url"] = s3.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.AWS_S3_BUCKET_NAME,
                    "Key": image_key
                },
                ExpiresIn=3600  
            )
        else:
            room["image_url"] = None
    
        booking = bookings_table.query(
            IndexName="roomId-index",   \
            KeyConditionExpression=boto3.dynamodb.conditions.Key('roomId').eq(room["roomId"]),
            ScanIndexForward=False,
            Limit=1
        ).get("Items", [])

        if booking:
            room["payment_status"] = booking[0]["payment_status"]
        else:
            room["payment_status"] = "AVAILABLE"

    return render(request, "reservations/list_room_types.html", {"rooms": rooms, "email": email})
    
lambda_client = boto3.client("lambda", region_name=settings.AWS_REGION)

@unauthenticated_user
def book_room(request, room_id):
    email = request.session.get("email")
    if request.method == "POST":

        start_date = request.POST["start_date"]
        end_date = request.POST["end_date"]

        payload = {
            "roomId": room_id,
            "start_date": start_date,
            "end_date": end_date,
        }

        # --- Call Lambda directly ---
        response = lambda_client.invoke(
            FunctionName=settings.LAMBDA_BOOK_ROOM,  # add in settings
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        raw = response["Payload"].read()
        outer = json.loads(raw)

        inner = json.loads(outer["body"])

        booking_id = inner.get("bookingId")
        total_price = inner.get("total_price")
        number_of_days = inner.get("number_of_days")
        
        if not booking_id:
            return HttpResponse("Booking failed: " + str(inner))

        return redirect(f"/payment/{booking_id}/{total_price}")

    return render(request, "reservations/book_room.html", {"room_id": room_id, "email": email})

SNS_TOPIC_ARN = settings.SNS_TOPIC_ARN
    
@unauthenticated_user
def payment(request, booking_id, total_price):
    email = request.session.get("email")
    if request.method == "POST":
        payload = {"bookingId": booking_id}

        response = lambda_client.invoke(
            FunctionName=settings.LAMBDA_PAYMENT,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        inner = json.loads(response["Payload"].read())

        status = inner.get("status")

        message = (
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

        return render(request, "reservations/payment_success.html", {"booking_id": booking_id, "total_price": total_price, "status": status})

    return render(request, "reservations/payment.html", {"booking_id": booking_id, "total_price": total_price, "email": email})


@unauthenticated_user
def payment_success(request):
    email = request.session.get("email")
    return render(request, "payment_success.html", {"email": email})


def room_search(request):
    email = request.session.get("email")
    search_engine = roomsearch.RoomSearchEngine()

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
            
    return render(request, "reservations/room_search.html", {"results": results, "filters": filters, "email": email})
