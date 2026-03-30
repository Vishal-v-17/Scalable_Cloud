import requests
from typing import Optional

class RoomSearchClient:

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        """
        base_url : URL where the Room Search API is running
                   e.g. "http://localhost:8000" or "https://api.yoursite.com"
        api_key  : optional Bearer token if auth is enabled
        """
        self.base_url = base_url.rstrip("/")
        self.session  = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"

    def search(
        self,
        # AWS config — omit to use API's own .env (your project)
        aws_access_key: str   = None,
        aws_secret_key: str   = None,
        aws_region:     str   = None,
        table_name:     str   = None,
        # Filters
        occupancy:      int   = None,
        bed_size:       str   = None,
        layout:         str   = None,
        rating:         float = None,
        min_price:      float = None,
        max_price:      float = None,
        keyword:        str   = None,
        wifi:           bool  = None,
    ) -> dict:

        # Build aws_config block only if credentials are provided
        aws_config = None
        if all([aws_access_key, aws_secret_key, aws_region, table_name]):
            aws_config = {
                "aws_access_key": aws_access_key,
                "aws_secret_key": aws_secret_key,
                "aws_region":     aws_region,
                "table_name":     table_name,
            }

        payload = {
            "aws_config": aws_config,
            "filters": {
                k: v for k, v in {
                    "occupancy":  occupancy,
                    "bed_size":   bed_size,
                    "layout":     layout,
                    "rating":     rating,
                    "min_price":  min_price,
                    "max_price":  max_price,
                    "keyword":    keyword,
                    "wifi":       str(wifi).lower() if wifi is not None else None,
                }.items() if v is not None
            }
        }

        response = self.session.post(f"{self.base_url}/rooms/search", json=payload)
        response.raise_for_status()
        return response.json()