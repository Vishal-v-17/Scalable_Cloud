import requests
import boto3
from botocore.exceptions import ClientError
from django.shortcuts import render

# ── Config ────────────────────────────────────────────────────────────────────
API_URL    = "https://tdks0jnlf2.execute-api.us-east-1.amazonaws.com/search"
S3_BUCKET  = "myhotel-room-images"
s3_client  = boto3.client("s3", region_name="us-east-1")


# ── Helpers ───────────────────────────────────────────────────────────────────
def generate_presigned_url(image_key, expiry=3600):
    """Generate a presigned URL for a private S3 object."""
    try:
        return s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": image_key},
            ExpiresIn=expiry,
        )
    except ClientError as e:
        print(f"Could not generate presigned URL: {e}")
        return None


def search_rooms(filters: dict) -> list:
    """
    POST filters to the Lambda search endpoint.
    Strips empty/null/any values before sending.
    Attaches a presigned S3 URL to each room result.
    """
    clean_filters = {k: v for k, v in filters.items() if v not in [None, "", "any"]}

    try:
        response = requests.post(
            API_URL,
            json={"filters": clean_filters},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        if response.status_code == 200:
            rooms = response.json().get("results", [])

            # Attach presigned image URL to every room
            for room in rooms:
                image_key = room.get("image_key")
                room["image_url"] = generate_presigned_url(image_key) if image_key else None

            return rooms

        print(f"API error {response.status_code}: {response.text}")
        return []

    except requests.exceptions.Timeout:
        print("Request timed out")
        return []
    except requests.exceptions.ConnectionError:
        print("Could not connect to API Gateway")
        return []
    except Exception as e:
        print(f"Unexpected error: {e}")
        return []


