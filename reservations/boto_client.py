import boto3
from django.conf import settings

def get_dynamodb():
    """Always returns a fresh DynamoDB resource."""
    return boto3.resource("dynamodb", region_name=settings.AWS_REGION)

def get_s3():
    """Always returns a fresh S3 client."""
    return boto3.client("s3", region_name=settings.AWS_REGION)

def get_lambda():
    """Always returns a fresh Lambda client."""
    return boto3.client("lambda", region_name=settings.AWS_REGION)

def get_table(table_name: str):
    """Always returns a fresh DynamoDB table."""
    return get_dynamodb().Table(table_name)
    
def get_cognito():
    """Always returns a fresh Cognito client."""
    return boto3.client("cognito-idp", region_name=settings.COGNITO_REGION)

def get_sns():
    """Always returns a fresh SNS client."""
    return boto3.client("sns", region_name=settings.AWS_REGION)