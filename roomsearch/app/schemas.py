from pydantic import BaseModel
from typing import Optional, List, Any

class AWSConfig(BaseModel):
    aws_access_key: str
    aws_secret_key: str
    aws_region:     str
    table_name:     str

class SearchFilters(BaseModel):
    occupancy:  Optional[str]   = None
    bed_size:   Optional[str]   = None
    layout:     Optional[str]   = None
    rating:     Optional[str]   = None
    min_price:  Optional[str]   = None
    max_price:  Optional[str]   = None
    keyword:    Optional[str]   = None
    wifi:       Optional[str]   = None

class SearchRequest(BaseModel):
    aws_config:          Optional[AWSConfig] = None  # None = use .env (your project)
    filters:             SearchFilters
    generate_image_urls: bool = False                # ← your project sets this to True

class RoomResult(BaseModel):
    image_url:   Optional[str] = None               # presigned S3 URL
    layout:      Optional[str] = None
    bed_size:    Optional[str] = None
    occupancy:   Optional[Any] = None
    rating:      Optional[Any] = None
    price:       Optional[Any] = None
    description: Optional[str] = None

class SearchResponse(BaseModel):
    table_name: str
    aws_region: str
    count:      int
    results:    List[Any]