from fastapi import FastAPI

from app.api.review import router

app = FastAPI(title="Financial Document Review API", version="0.1.0")
app.include_router(router, prefix="/api")
