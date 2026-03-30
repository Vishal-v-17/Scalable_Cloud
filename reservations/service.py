import requests
import boto3
from botocore.exceptions import ClientError

API_URL = "https://tdks0jnlf2.execute-api.us-east-1.amazonaws.com/search"

S3_BUCKET = "myhotel-room-images"
s3_client = boto3.client("s3", region_name="us-east-1")

def generate_presigned_url(image_key, expiry=3600):
    """Generate a presigned URL for a private S3 object"""
    try:
        url = s3_client.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": image_key},
            ExpiresIn=expiry  # valid for 1 hour
        )
        return url
    except ClientError as e:
        print(f"Could not generate presigned URL: {e}")
        return None

def search_rooms(filters):
    clean_filters = {k: v for k, v in filters.items() if v not in [None, "", "any"]}

    try:
        response = requests.post(
            API_URL,
            json={"filters": clean_filters},
            headers={"Content-Type": "application/json"},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            rooms = data.get("rooms", [])

            # ── Replace image_key with a boto3 presigned URL ──────
            for room in rooms:
                image_key = room.get("image_key")
                if image_key:
                    room["image_url"] = generate_presigned_url(image_key)
                else:
                    room["image_url"] = None

            return rooms
        else:
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