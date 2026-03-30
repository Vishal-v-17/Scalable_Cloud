import traceback
from fastapi import APIRouter, HTTPException
from .schemas  import SearchRequest, SearchResponse
from .engine   import RoomSearchEngine
from .image_service import ImageService

router = APIRouter(prefix="/rooms", tags=["Rooms"])

@router.post("/search", response_model=SearchResponse)
def search_rooms(request: SearchRequest):
    try:
        aws_config = request.aws_config.dict() if request.aws_config else None

        # ── Search DynamoDB ────────────────────────────────────────────────
        engine       = RoomSearchEngine(aws_config=aws_config)
        filters_dict = request.filters.dict(exclude_none=True)
        results      = engine.search(filters_dict)

        # ── Attach presigned S3 image URLs (your project only) ────────────
        if request.generate_image_urls:
            image_service = ImageService(aws_config=aws_config)
            results       = image_service.attach_image_urls(results)

        return {
            "table_name": engine.table_name,
            "aws_region": engine.aws_region,
            "count":      len(results),
            "results":    results,
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))