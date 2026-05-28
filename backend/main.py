"""
shorts-agent FastAPI 진입점
1단계 MVP: 주제 발굴 (4개 소스 수집 + 후보 조회)
"""
import sys
import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import database
from api.routes import topics, angles
from services import scheduler_service

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.init_db()
    scheduler_service.start()
    yield


app = FastAPI(title="shorts-agent", version="0.2.0", lifespan=lifespan)
app.include_router(topics.router)
app.include_router(angles.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "shorts-agent", "version": "0.2.0",
            "db": "postgresql" if database.IS_PG else "sqlite"}


# 프론트엔드 정적 파일
if os.path.isdir(os.path.join(FRONTEND_DIR, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")


@app.get("/")
def index():
    idx = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(idx):
        return FileResponse(idx)
    return {"service": "shorts-agent", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=True)
