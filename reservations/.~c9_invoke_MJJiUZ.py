import os
from decimal import Decimal
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StructField,
    StringType, BooleanType, DoubleType
)

os.environ['SPARK_HOME'] = os.path.expanduser(
    '~/environment/Project_code/spark-3.5.8-bin-hadoop3'
)

def get_spark():
    return SparkSession.builder \
        .appName("HotelReport") \
        .master("local[*]") \
        .config("spark.driver.memory", "1g") \
        .config("spark.ui.enabled", "false") \
        .getOrCreate()


def clean_rooms(raw_items: list) -> list:
    """
    DynamoDB returns Decimal types — convert everything
    to plain Python types so Spark can read them.
    """
    cleaned = []
    for item in raw_items:
        cleaned.append({
            "roomId":      str(item.get("roomId", "")),
            "bed_size":    str(item.get("bed_size", "Unknown")),
            "layout":      str(item.get("layout", "Unknown")),
            "occupancy":   str(item.get("occupancy", "Unknown")),
            "price":       float(str(item.get("price", 0))),
            "rating":      float(str(item.get("rating", 0))),
            "wifi":        bool(item.get("wifi", False)),
            "description": str(item.get("description", "")),
            "image_key":   str(item.get("image_key", "")),
        })
    return cleaned


def clean_bookings(raw_items: list) -> list:
    """
    Convert Bookings DynamoDB items to plain Python dicts.
    Will return empty list if no bookings yet — handled gracefully.
    """
    cleaned = []
    for item in raw_items:
        cleaned.append({
            "bookingId":   str(item.get("bookingId", "")),
            "roomId":      str(item.get("roomId", "")),
            "guestName":   str(item.get("guestName", "Unknown")),
            "checkIn":     str(item.get("checkIn", "")),
            "checkOut":    str(item.get("checkOut", "")),
            "totalPrice":  float(str(item.get("totalPrice", 0))),
            "status":      str(item.get("status", "Unknown")),
        })
    return cleaned


def generate_hotel_report(raw_rooms: list, raw_bookings: list) -> dict:
    """
    Main report function. Accepts raw DynamoDB items from both tables.
    Returns a dict of report sections for Django to display.
    """
    spark = get_spark()
    spark.sparkContext.setLogLevel("ERROR")

    # --- Clean the data ---
    rooms     = clean_rooms(raw_rooms)
    bookings  = clean_bookings(raw_bookings)

    # ── ROOMS DATAFRAME ──────────────────────────────────────────
    room_schema = StructType([
        StructField("roomId",      StringType(),  True),
        StructField("bed_size",    StringType(),  True),
        StructField("layout",      StringType(),  True),
        StructField("occupancy",   StringType(),  True),
        StructField("price",       DoubleType(),  True),
        StructField("rating",      DoubleType(),  True),
        StructField("wifi",        BooleanType(), True),
        StructField("description", StringType(),  True),
        StructField("image_key",   StringType(),  True),
    ])

    rooms_df = spark.createDataFrame(rooms, schema=room_schema)

    # 1. Overall hotel summary
    overall = rooms_df.agg(
        F.count("*").alias("total_rooms"),
        F.round(F.avg("price"),  2).alias("avg_price"),
        F.min("price").alias("cheapest_room"),
        F.max("price").alias("most_expensive_room"),
        F.round(F.avg("rating"), 2).alias("avg_rating"),
        F.max("rating").alias("top_rating"),
        F.sum(F.when(F.col("wifi") == True, 1).otherwise(0)).alias("rooms_with_wifi"),
        F.sum(F.when(F.col("wifi") == False, 1).otherwise(0)).alias("rooms_without_wifi"),
    ).collect()[0].asDict()

    # 2. Rooms by bed size
    by_bed_size = rooms_df.groupBy("bed_size").agg(
        F.count("*").alias("total_rooms"),
        F.round(F.avg("price"),  2).alias("avg_price"),
        F.round(F.avg("rating"), 2).alias("avg_rating"),
        F.min("price").alias("min_price"),
        F.max("price").alias("max_price"),
    ).orderBy("total_rooms", ascending=False)

    # 3. Rooms by layout
    by_layout = rooms_df.groupBy("layout").agg(
        F.count("*").alias("total_rooms"),
        F.round(F.avg("price"),  2).alias("avg_price"),
        F.round(F.avg("rating"), 2).alias("avg_rating"),
    ).orderBy("avg_price", ascending=False)

    # 4. Rooms by occupancy
    by_occupancy = rooms_df.groupBy("occupancy").agg(
        F.count("*").alias("total_rooms"),
        F.round(F.avg("price"),  2).alias("avg_price"),
        F.round(F.avg("rating"), 2).alias("avg_rating"),
    ).orderBy("avg_price", ascending=False)

    # 5. Top rated rooms
    top_rated = rooms_df.orderBy("rating", ascending=False) \
                        .select("roomId", "bed_size", "layout",
                                "occupancy", "price", "rating", "wifi") \
                        .limit(5)

    # 6. Best value rooms (high rating, lower price)
    best_value = rooms_df.filter(F.col("rating") >= 4.0) \
                         .orderBy("price") \
                         .select("roomId", "bed_size", "layout",
                                 "occupancy", "price", "rating") \
                         .limit(5)

    # ── BOOKINGS DATAFRAME (only if data exists) ──────────────────
    booking_stats = {}
    room_booking_summary = []

    if bookings:
        booking_schema = StructType([
            StructField("bookingId",  StringType(), True),
            StructField("roomId",     StringType(), True),
            StructField("guestName",  StringType(), True),
            StructField("checkIn",    StringType(), True),
            StructField("checkOut",   StringType(), True),
            StructField("totalPrice", DoubleType(), True),
            StructField("status",     StringType(), True),
        ])

        bookings_df = spark.createDataFrame(bookings, schema=booking_schema)

        # Overall booking stats
        booking_stats = bookings_df.agg(
            F.count("*").alias("total_bookings"),
            F.round(F.sum("totalPrice"),  2).alias("total_revenue"),
            F.round(F.avg("totalPrice"),  2).alias("avg_booking_value"),
        ).collect()[0].asDict()

        # Bookings per room (join with rooms)
        room_booking_summary = bookings_df.groupBy("roomId").agg(
            F.count("*").alias("times_booked"),
            F.round(F.sum("totalPrice"), 2).alias("revenue_generated"),
        ).join(
            rooms_df.select("roomId", "bed_size", "layout", "occupancy", "price"),
            on="roomId", how="left"
        ).orderBy("times_booked", ascending=False)
        room_booking_summary = [r.asDict() for r in room_booking_summary.collect()]

    # ── ASSEMBLE RESULT ───────────────────────────────────────────
    result = {
        "overall":              overall,
        "by_bed_size":          [r.asDict() for r in by_bed_size.collect()],
        "by_layout":            [r.asDict() for r in by_layout.collect()],
        "by_occupancy":         [r.asDict() for r in by_occupancy.collect()],
        "top_rated":            [r.asDict() for r in top_rated.collect()],
        "best_value":           [r.asDict() for r in best_value.collect()],
        "booking_stats":        booking_stats,
        "room_booking_summary": room_booking_summary,
        "has_bookings":         len(bookings) > 0,
    }

    spark.stop()
    return result