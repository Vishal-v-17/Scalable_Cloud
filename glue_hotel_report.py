import boto3
import json
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField,
    StringType, DoubleType, IntegerType
)

sc          = SparkContext()
glueContext = GlueContext(sc)
spark       = glueContext.spark_session
spark.sparkContext.setLogLevel("ERROR")

dynamodb       = boto3.resource("dynamodb", region_name="us-east-1")
bookings_table = dynamodb.Table("Bookings")

S3_BUCKET = "aws-glue-assets-992382373831-us-east-1"
S3_KEY    = "reports/hotel_report.json"

raw_bookings = bookings_table.scan().get("Items", [])

def clean_bookings(raw_items):
    cleaned = []
    for item in raw_items:
        cleaned.append({
            "bookingId":      str(item.get("bookingId",      "")),
            "roomId":         str(item.get("roomId",         "")),
            "start_date":     str(item.get("start_date",     "")),
            "end_date":       str(item.get("end_date",       "")),
            "number_of_days": int(str(item.get("number_of_days", 0))),
            "total_price":    float(str(item.get("total_price",   0))),
            "payment_status": str(item.get("payment_status", "UNKNOWN")),
        })
    return cleaned

bookings = clean_bookings(raw_bookings)

booking_schema = StructType([
    StructField("bookingId",      StringType(),  True),
    StructField("roomId",         StringType(),  True),
    StructField("start_date",     StringType(),  True),
    StructField("end_date",       StringType(),  True),
    StructField("number_of_days", IntegerType(), True),
    StructField("total_price",    DoubleType(),  True),
    StructField("payment_status", StringType(),  True),
])

bookings_df = spark.createDataFrame(bookings, schema=booking_schema)

# ── Overall summary ───────────────────────────────────────────────
overall = bookings_df.agg(
    F.count("*")                                              .alias("total_bookings"),
    F.round(F.sum("total_price"),    2)                       .alias("total_revenue"),
    F.round(F.avg("total_price"),    2)                       .alias("avg_booking_value"),
    F.round(F.avg("number_of_days"), 2)                       .alias("avg_stay_days"),
    F.min("total_price")                                      .alias("cheapest_booking"),
    F.max("total_price")                                      .alias("most_expensive_booking"),
    F.sum(F.when(F.col("payment_status") == "CONFIRMED", 1)
           .otherwise(0))                                     .alias("confirmed_bookings"),
    F.sum(F.when(F.col("payment_status") == "CANCELLED", 1)
           .otherwise(0))                                     .alias("cancelled_bookings"),
    F.sum(F.when(F.col("payment_status") == "PENDING",   1)
           .otherwise(0))                                     .alias("pending_bookings"),
).collect()[0].asDict()

# ── Bookings by payment status ────────────────────────────────────
by_status = (
    bookings_df
    .groupBy("payment_status")
    .agg(
        F.count("*")                     .alias("count"),
        F.round(F.sum("total_price"), 2) .alias("total_revenue"),
        F.round(F.avg("total_price"), 2) .alias("avg_price"),
    )
    .orderBy(F.desc("count"))
    .collect()
)
by_status_list = [row.asDict() for row in by_status]

# ── Most booked rooms ─────────────────────────────────────────────
top_rooms = (
    bookings_df
    .groupBy("roomId")
    .agg(
        F.count("*")                     .alias("booking_count"),
        F.round(F.sum("total_price"), 2) .alias("total_revenue"),
        F.round(F.avg("number_of_days"), 1).alias("avg_stay_days"),
    )
    .orderBy(F.desc("booking_count"))
    .limit(5)
    .collect()
)
top_rooms_list = [row.asDict() for row in top_rooms]

# ── Recent bookings ───────────────────────────────────────────────
recent = (
    bookings_df
    .orderBy(F.desc("start_date"))
    .limit(10)
    .collect()
)
recent_list = [row.asDict() for row in recent]

# ── Assemble result ───────────────────────────────────────────────
result = {
    "overall":      overall,
    "by_status":    by_status_list,
    "top_rooms":    top_rooms_list,
    "recent":       recent_list,
    "has_bookings": len(bookings) > 0,
}

s3 = boto3.client("s3")
s3.put_object(
    Bucket=S3_BUCKET,
    Key=S3_KEY,
    Body=json.dumps(result, indent=2, default=str),
    ContentType="application/json"
)
print(f"Report saved to s3://{S3_BUCKET}/{S3_KEY}")