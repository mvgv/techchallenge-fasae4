"""Aplicação FastAPI do MedWatch."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from medwatch import db
from medwatch.api import routes_alerts, routes_media, routes_patients
from medwatch.api.deps import get_bus
from medwatch.logging_setup import setup_logging

setup_logging("api")

app = FastAPI(title="MedWatch")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"],
                   allow_headers=["*"])
app.include_router(routes_patients.router)
app.include_router(routes_media.router)
app.include_router(routes_alerts.router)


@app.get("/health")
def health() -> dict:
    try:
        redis_ok = bool(get_bus().r.ping())
    except Exception:
        redis_ok = False
    return {"status": "ok", "db": db.ping(), "redis": redis_ok}
