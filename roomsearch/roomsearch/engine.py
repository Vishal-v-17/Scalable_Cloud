from . import boto3, Decimal, settings

class RoomSearchEngine:
    
    def __init__(self):
        
        self.dynamodb = boto3.resource("dynamodb",region_name=settings.AWS_REGION)
        self.table = self.dynamodb.Table(settings.AWS_DYNAMODB_TABLE)
    
    def search(self, filters):

        response = self.table.scan()
        rooms = response.get("Items", [])

        occ_filter     = filters.get("occupancy")
        bed_filter     = filters.get("bed_size")
        layout_filter  = filters.get("layout")
        rating_filter  = filters.get("rating")
        min_price      = filters.get("min_price")
        max_price      = filters.get("max_price")
        keyword        = filters.get("keyword", "").strip().lower()

        wifi_val = filters.get("wifi")
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

            if min_price and Decimal(room.get("price")) < Decimal(min_price):
                return False

            if max_price and Decimal(room.get("price")) > Decimal(max_price):
                return False

            if rating_filter and str(room.get("rating")) <= str(rating_filter):
                return False

            if keyword and keyword not in room.get("description", "").lower():
                return False

            return True

        return [room for room in rooms if match(room)]
