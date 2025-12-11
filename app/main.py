from fastapi import FastAPI
from app.router import apply_cors, router

app = FastAPI(
    title="AI Project Builder",
    version="1.0.0",
)
apply_cors(app)


app.include_router(router)

