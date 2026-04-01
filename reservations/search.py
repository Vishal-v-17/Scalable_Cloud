import boto3
from decimal import Decimal
from django.conf import settings


def get_dynamodb():
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION)

def get_s3():
    return boto3.client("s3", region_name=settings.AWS_REGION)


def fetch_rooms() -> list:
    """
    Fetches all rooms from DynamoDB and attaches
    a presigned S3 image URL using image_key.
    Returns a plain JSON-safe list ready to send to Lambda.
    """
    dynamodb = get_dynamodb()
    s3       = get_s3()
    table    = dynamodb.Table(settings.AWS_DYNAMODB_TABLE)

    # ── Scan all rooms ─────────────────────────────────────────────────────
    response = table.scan()
    rooms    = response.get("Items", [])

    # ── Handle DynamoDB pagination ─────────────────────────────────────────
    while "LastEvaluatedKey" in response:
        response = table.scan(
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        rooms.extend(response.get("Items", []))

    # ── Process each room ──────────────────────────────────────────────────
    processed = []
    for room in rooms:

        # Convert Decimal → float for JSON compatibility
        room = convert_decimals(room)
        
        if "wifi" in room:
            room["wifi"] = "true" if room["wifi"] else "false"
            
        # Attach presigned S3 image URL
        image_key = room.get("image_key")
        if image_key:
            room["image_url"] = s3.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": settings.AWS_S3_BUCKET_NAME,
                    "Key":    image_key,
                },
                ExpiresIn=3600
            )
        else:
            room["image_url"] = None

        processed.append(room)

    return processed


def convert_decimals(obj):
    """Recursively convert DynamoDB Decimal to float."""
    if isinstance(obj, list):
        return [convert_decimals(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: convert_decimals(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return float(obj)
    return obj