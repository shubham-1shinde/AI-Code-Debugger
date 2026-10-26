import logging
from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.debug import router

load_dotenv()


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    force=True,
)


app = FastAPI(
    title="AI Code Debugger",
    version="1.0.0",
)

app.include_router(router, prefix="/api")


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "AI Code Debugger",
    }
