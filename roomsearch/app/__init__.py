import boto3
from decimal import Decimal
import django
import os
import sys

# ── Load Django settings from hotel_site/settings.py ─────────────────────────
sys.path.insert(0, "/home/ec2-user/environment/Project_code")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hotel_site.settings")
django.setup()

from django.conf import settings as django_settings

class _Settings:
    AWS_REGION         = django_settings.AWS_REGION
    AWS_DYNAMODB_TABLE = django_settings.AWS_DYNAMODB_TABLE
    AWS_S3_BUCKET_NAME = django_settings.AWS_S3_BUCKET_NAME

settings = _Settings()
__all__  = ["boto3", "Decimal", "settings"]