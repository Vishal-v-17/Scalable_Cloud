from . import boto3, Decimal, settings

class RoomSearchEngine:

    def __init__(self, aws_config: dict = None):
        if aws_config:
            # Other project's own AWS account + table
            self.dynamodb = boto3.resource(
                "dynamodb",
                region_name=          aws_config["aws_region"],
                aws_access_key_id=    aws_config["aws_access_key"],
                aws_secret_access_key=aws_config["aws_secret_key"],
            )
            self.table_name = aws_config["table_name"]
            self.aws_region = aws_config["aws_region"]
        else:
            # Your own project — fallback to .env
            self.dynamodb   = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
            self.table_name = settings.AWS_DYNAMODB_TABLE
            self.aws_region = settings.AWS_REGION

        self.table = self.dynamodb.Table(self.table_name)

    def search(self, filters: dict) -> list:
        response = self.table.scan()
        rooms    = response.get("Items", [])

        occ_filter    = filters.get("occupancy")
        bed_filter    = filters.get("bed_size")
        layout_filter = filters.get("layout")
        rating_filter = filters.get("rating")
        min_price     = filters.get("min_price")
        max_price     = filters.get("max_price")
        keyword       = filters.get("keyword", "").strip().lower()

        wifi_val    = filters.get("wifi")
        wifi_filter = None
        if wifi_val == "true":
            wifi_filter = True
        elif wifi_val == "false":
            wifi_filter = False

        def match(room):
            if occ_filter and str(room.get("occupancy")) != str(occ_filter):
                return False
            if bed_filter and room.get("bed_size") != bed_filter:
                return False
            if layout_filter and room.get("layout", "").lower() != layout_filter.lower():
                return False
            if wifi_filter is not None and room.get("wifi") != wifi_filter:
                return False
            if min_price and Decimal(str(room.get("price", 0))) < Decimal(str(min_price)):
                return False
            if max_price and Decimal(str(room.get("price", 0))) > Decimal(str(max_price)):
                return False
            if rating_filter and float(room.get("rating", 0)) <= float(rating_filter):
                return False
            if keyword and keyword not in room.get("description", "").lower():
                return False
            return True

        return [room for room in rooms if match(room)]