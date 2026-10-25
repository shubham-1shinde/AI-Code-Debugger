
from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.debug import router

load_dotenv()

app = FastAPI(
    title="AI Production Debugger",
    version="1.0.0",
)

app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "AI Production Debugger",
    }
