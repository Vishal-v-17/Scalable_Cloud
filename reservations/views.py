from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import BookingForm, RoomForm
from .models import Room, Booking, Payment, RoomStatus, RoomType
from .decorators import cognito_email_allowed, unauthenticated_user
from .search import fetch_rooms
from .spark_report import (trigger_glue_job,fetch_report_from_s3,get_latest_job_status,)
import logging
from django.core.cache import cache
from django.http import JsonResponse

from datetime import date

#cognito
import hmac
import hashlib
import re

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


client = boto3.client("cognito-idp", region_name=settings.COGNITO_REGION)
sns = boto3.client("sns", region_name="us-east-1")

def get_dynamodb():
    """Always creates fresh boto3 resource — handles AWS Academy session restarts."""
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION)

def get_s3():
    """Always creates fresh boto3 client — handles AWS Academy session restarts."""
    return boto3.client("s3", region_name=settings.AWS_REGION)

def lambda_client():
    """Always returns a fresh Lambda client."""
    return boto3.client("lambda", region_name=settings.AWS_REGION)

def get_table(table_name: str):
    """Always returns a fresh DynamoDB table."""
    return get_dynamodb().Table(table_name)

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

def is_valid_password(password):
    if len(password) < 8:
        return False
    if not re.search(r"[A-Z]", password):
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[0-9]", password):
        return False
    if not re.search(r"[!@#$%^&*]", password):
        return False
    return True

def signup(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")
        
        if not is_valid_password(password):
            return render(request, "reservations/signup.html", {
                "error": "Password must include uppercase, lowercase, number, and special character"
            })

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

#@cognito_email_allowed(['cpphotelproject@gmail.com'])
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

def list_rooms(request):
    email = request.session.get("email")
    
    table          = get_table(settings.AWS_DYNAMODB_TABLE)
    bookings_table = get_table(settings.AWS_DYNAMODB_TABLE_1)
    s3      = get_s3()
    
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

OFFERS_API_URL = "https://yjb1bzfi1i.execute-api.us-east-1.amazonaws.com/offers"

def get_seasonal_offer(start_date):
    try:
        response = requests.get(OFFERS_API_URL, timeout=5)
        response.raise_for_status()
        offers = response.json().get("available_offers", {})
    except Exception:
        return None, 0

    season_map = {
        1:  ["New Year", "Pongal"],
        2:  ["Valentine's Day"],
        3:  ["Women's Day", "Easter"],
        4:  ["Easter", "Summer Sale"],
        5:  ["Summer Sale"],
        6:  ["Summer Sale"],
        10: ["Halloween", "Diwali"],
        11: ["Diwali", "Black Friday"],
        12: ["Cyber Monday", "Christmas"],
    }

    best_offer, best_discount = None, 0
    for offer_name in season_map.get(start_date.month, []):
        discount = offers.get(offer_name, 0)
        if discount > best_discount:
            best_discount = discount
            best_offer = offer_name

    return best_offer, best_discount
    
lambda_client = boto3.client("lambda", region_name=settings.AWS_REGION)

@unauthenticated_user
def book_room(request, room_id):
    email = request.session.get("email")
    
    # Fetch offers to show hint on the booking page
    import json as _json
    try:
        api_resp = requests.get(OFFERS_API_URL, timeout=5)
        offers = api_resp.json().get("available_offers", {})
    except Exception:
        offers = {}
        
    if request.method == "POST":
        start_date = request.POST["start_date"]
        end_date = request.POST["end_date"]

        # --- Fetch seasonal offer ---
        offer_name, discount_rate = get_seasonal_offer(
            date.fromisoformat(start_date)
        )

        payload = {
            "roomId": room_id,
            "start_date": start_date,
            "end_date": end_date,
        }

        # --- Call Lambda directly ---
        response = lambda_client.invoke(
            FunctionName=settings.LAMBDA_BOOK_ROOM,
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

        # --- Apply discount to total_price ---
        if discount_rate and total_price:
            original_price = float(total_price)
            discount_amount = round(original_price * discount_rate, 2)
            discounted_price = round(original_price - discount_amount, 2)

            # Store offer details in session for confirmation page
            request.session["offer_data"] = {
                "offer_name":      offer_name,
                "discount_rate":   discount_rate,
                "original_price":  original_price,
                "discount_amount": discount_amount,
                "final_price":     discounted_price,
            }

            # With this — removes unnecessary .0 for whole numbers
            final = int(discounted_price) if discounted_price == int(discounted_price) else discounted_price
            return redirect(f"/payment/{booking_id}/{final}")

        # No offer available, proceed with original price
        request.session.pop("offer_data", None)
        return redirect(f"/payment/{booking_id}/{total_price}")

    return render(request, "reservations/book_room.html", {"room_id": room_id, "email": email})

SNS_TOPIC_ARN = settings.SNS_TOPIC_ARN
    
@unauthenticated_user
def payment(request, booking_id, total_price):
    email = request.session.get("email")
    offer_data = request.session.get("offer_data", None)
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

    return render(request, "reservations/payment.html", {"booking_id": booking_id, "total_price": total_price,"offer_data": offer_data, "email": email})


@unauthenticated_user
def payment_success(request):
    email = request.session.get("email")
    return render(request, "payment_success.html", {"email": email})

LAMBDA_SEARCH_URL = "https://07wn5poyr7.execute-api.us-east-1.amazonaws.com/search"

def room_search(request):
    email   = request.session.get("email")
    results = None
    count   = 0
    error   = None

    # ── Read filters from GET params ───────────────────────────────────────
    filters = {
        key: val
        for key in ["keyword", "occupancy", "bed_size",
                    "layout", "wifi", "min_price", "max_price", "rating"]
        if (val := request.GET.get(key, "").strip())
    }

    if request.GET:
        try:
            # Step 1 — Fetch rooms from DynamoDB + S3 image URLs
            rooms = fetch_rooms()

            # Step 2 — Send data + filters to Lambda search API
            response = requests.post(
                LAMBDA_SEARCH_URL,
                json={
                    "data":    rooms,    # full room list with image_url attached
                    "filters": filters,
                },
                timeout=10
            )
            response.raise_for_status()
            data    = response.json()
            results = data["results"]   # already has image_url in each room
            count   = data["count"]

        except requests.exceptions.RequestException as e:
            error = f"Search API error: {str(e)}"
        except Exception as e:
            error = f"Error: {str(e)}"

    return render(request, "reservations/room_search.html", {
        "results": results,
        "filters": filters,
        "count":   count,
        "email":   email,
        "error":   error,
    })

    
def map_view(request):
    email = request.session.get("email")
    return render(request, "reservations/map.html", {"google_maps_api_key": settings.GOOGLE_MAPS_API_KEY, "email": email})

def glue_report(request):
    error      = None
    report     = {}
    overall    = {}
    job_status = None
    
    email   = request.session.get("email")
    
    try:
        job_status = get_latest_job_status()
    except Exception as e:
        job_status = {"state": "ERROR", "error": str(e),
                      "run_id": "", "started": "", "ended": ""}

    try:
        report  = fetch_report_from_s3()
        overall = report.get("overall", {})
    except RuntimeError as e:
        error = str(e)
    except Exception as e:
        error = f"Unexpected error: {e}"

    return render(request, "reservations/report.html", {
        "overall":      overall,
        "by_status":    report.get("by_status",  []),
        "top_rooms":    report.get("top_rooms",  []),
        "recent":       report.get("recent",     []),
        "has_bookings": report.get("has_bookings", False),
        "error":        error,
        "job_status":   job_status,
        "cooldown_active": bool(cache.get("glue_job_cooldown")),
        "email":   email,
    })


def run_glue_job(request):
    """Manually trigger the Glue job — returns JSON."""
    if request.method == "POST":
        try:
            run_id = trigger_glue_job()
            cache.set("glue_job_cooldown", True, 120)
            return JsonResponse({
                "success": True,
                "run_id":  run_id,
                "message": "Glue job started."
            })
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=500)
    return JsonResponse({"success": False, "message": "POST required"}, status=405)


def glue_job_status(request):
    """Return current Glue job status as JSON — polled by frontend."""
    try:
        status = get_latest_job_status()
        if status is None:
            return JsonResponse({"state": "NEVER_RUN", "error": ""})
        # Also tell frontend if a booking-triggered job is pending
        status["cooldown_active"] = bool(cache.get("glue_job_cooldown"))
        return JsonResponse(status)
    except Exception as e:
        return JsonResponse({"state": "ERROR", "error": str(e)}, status=500)