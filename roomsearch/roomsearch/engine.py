from . import boto3, Decimal, settings

class RoomSearchEngine:
    
    def __init__(self):
        
        self.dynamodb = boto3.resource("dynamodb",region_name=settings.AWS_REGION)
        self.table = self.dynamodb.Table(settings.AWS_DYNAMODB_TABLE)
    
    def search(self, filters):

        response = self.table.scan()
        items = response.get("Items", [])

        def match(item):
            for key, value in filters.items():

                item_value = item.get(key)

                # Skip empty filters
                if value is None or value == "":
                    continue

                # Handle numeric comparisons
                if isinstance(value, dict):
                    if "min" in value and Decimal(item_value) < Decimal(value["min"]):
                        return False
                    if "max" in value and Decimal(item_value) > Decimal(value["max"]):
                        return False

                # Handle string match (case-insensitive)
                elif isinstance(value, str):
                    if value.lower() not in str(item_value).lower():
                        return False

                # Exact match (numbers, booleans)
                else:
                    if item_value != value:
                        return False

            return True

        filtered_items = [item for item in items if match(item)]

        # 🔥 Convert to generic structure

        if not filtered_items:
            return {
                "columns": [],
                "data": []
            }

        # Dynamic columns
        all_keys = set()
        for item in filtered_items:
            all_keys.update(item.keys())

        columns = list(all_keys)

        data = [
            [item.get(col, None) for col in columns]
            for item in filtered_items
        ]

        return {
            "columns": columns,
            "data": data
        }