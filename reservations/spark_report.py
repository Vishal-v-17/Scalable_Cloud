# reservations/spark_report.py

import boto3
import json
import logging
from botocore.exceptions import ClientError, NoCredentialsError
from django.core.cache import cache

logger = logging.getLogger(__name__)

AWS_REGION    = "us-east-1"
GLUE_JOB_NAME = "hotel_report_job"
S3_BUCKET     = "aws-glue-assets-992382373831-us-east-1"
S3_KEY        = "reports/hotel_report.json"

COOLDOWN_KEY     = "glue_job_cooldown"
COOLDOWN_SECONDS = 120   # prevent duplicate jobs within 2 minutes


# ── Glue job controls ──────────────────────────────────────────────

def trigger_glue_job():
    client = boto3.client("glue", region_name=AWS_REGION)
    response = client.start_job_run(JobName=GLUE_JOB_NAME)
    run_id = response["JobRunId"]
    logger.info(f"Glue job started: {run_id}")
    return run_id


def get_job_status(run_id):
    client = boto3.client("glue", region_name=AWS_REGION)
    response = client.get_job_run(JobName=GLUE_JOB_NAME, RunId=run_id)
    run = response["JobRun"]
    return {
        "state":   run.get("JobRunState", "UNKNOWN"),
        "error":   run.get("ErrorMessage", ""),
        "started": str(run.get("StartedOn", "")),
        "ended":   str(run.get("CompletedOn", "")),
    }


def get_latest_job_status():
    """
    Returns status dict, None if never run,
    or a dict with state='ERROR' if credentials expired.
    """
    try:
        client = boto3.client("glue", region_name=AWS_REGION)
        response = client.get_job_runs(
            JobName=GLUE_JOB_NAME,
            MaxResults=1
        )
        runs = response.get("JobRuns", [])
        if not runs:
            return None
        run = runs[0]
        return {
            "state":   run.get("JobRunState", "UNKNOWN"),
            "error":   run.get("ErrorMessage", ""),
            "run_id":  run.get("Id", ""),
            "started": str(run.get("StartedOn", "")),
            "ended":   str(run.get("CompletedOn", "")),
        }
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code in ("ExpiredTokenException", "InvalidClientTokenId"):
            return {
                "state": "ERROR",
                "error": "AWS session token expired. Refresh your credentials in AWS Academy.",
                "run_id": "", "started": "", "ended": ""
            }
        return {
            "state": "ERROR",
            "error": str(e),
            "run_id": "", "started": "", "ended": ""
        }
    except NoCredentialsError:
        return {
            "state": "ERROR",
            "error": "No AWS credentials found. Run 'aws configure' in Cloud9.",
            "run_id": "", "started": "", "ended": ""
        }


def fetch_report_from_s3():
    """
    Returns parsed report dict.
    Raises a user-friendly RuntimeError on AWS auth issues.
    """
    try:
        s3 = boto3.client("s3", region_name=AWS_REGION)
        obj = s3.get_object(Bucket=S3_BUCKET, Key=S3_KEY)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "NoSuchKey":
            raise RuntimeError("Report not found in S3. Run the Glue job first.")
        if code in ("ExpiredTokenException", "InvalidClientTokenId"):
            raise RuntimeError(
                "AWS session token expired. Refresh your credentials in AWS Academy."
            )
        raise RuntimeError(str(e))
    except NoCredentialsError:
        raise RuntimeError(
            "No AWS credentials found. Run 'aws configure' in Cloud9."
        )


# ── Auto-trigger signal handler ────────────────────────────────────

def handle_booking_change(sender, instance, **kwargs):
    """
    Called by Django signals whenever a Booking is
    created, updated, or deleted.
    Triggers the Glue job with a 2-minute cooldown
    so rapid saves don't spawn duplicate jobs.
    """
    if cache.get(COOLDOWN_KEY):
        logger.info("Glue trigger skipped — cooldown active")
        return

    try:
        run_id = trigger_glue_job()
        cache.set(COOLDOWN_KEY, True, COOLDOWN_SECONDS)
        logger.info(
            f"Glue job auto-triggered on Booking "
            f"{sender.__name__} change. Run ID: {run_id}"
        )
    except Exception as e:
        # Never let a Glue failure break the booking save
        logger.error(f"Glue auto-trigger failed: {e}")