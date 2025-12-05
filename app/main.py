from fastapi import FastAPI
from app.router import router

app = FastAPI(
    title="AI Project Builder",
    version="1.0.0",
)

app.include_router(router)

