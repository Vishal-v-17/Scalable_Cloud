from fastapi import FastAPI
from .routes import router

app = FastAPI(
    title="Room Search API",
    description="Search room inventory from any DynamoDB table across AWS accounts",
    version="1.0.0",
)

app.include_router(router)

@app.get("/health")
def health():
    return {"status": "ok"}