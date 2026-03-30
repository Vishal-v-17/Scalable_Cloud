from . import boto3, settings

class ImageService:

    def __init__(self, aws_config: dict = None):
        if aws_config:
            # Other project's own S3 bucket
            self.s3_client  = boto3.client(
                "s3",
                region_name=          aws_config["aws_region"],
                aws_access_key_id=    aws_config["aws_access_key"],
                aws_secret_access_key=aws_config["aws_secret_key"],
            )
            self.bucket_name = aws_config.get("s3_bucket_name")
        else:
            # Your own project — use .env
            self.s3_client   = boto3.client("s3", region_name=settings.AWS_REGION)
            self.bucket_name = settings.AWS_S3_BUCKET_NAME

    def attach_image_urls(self, rooms: list, expires_in: int = 3600) -> list:
        """
        For each room, generate a presigned S3 URL from image_key.
        Mirrors exactly what your Django view does.
        """
        for room in rooms:
            image_key = room.get("image_key")
            if image_key and self.bucket_name:
                room["image_url"] = self.s3_client.generate_presigned_url(
                    "get_object",
                    Params={
                        "Bucket": self.bucket_name,
                        "Key":    image_key,
                    },
                    ExpiresIn=expires_in,
                )
            else:
                room["image_url"] = None
        return rooms