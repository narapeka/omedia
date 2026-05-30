from __future__ import annotations

from fastapi import APIRouter

from app.api.http.routers import activity, admin, depot, identify, inventory, organize, origin, rule, settings, transfer, watch

api_router = APIRouter()
api_router.include_router(settings.router)
api_router.include_router(origin.router)
api_router.include_router(depot.router)
api_router.include_router(rule.router)
api_router.include_router(inventory.router)
api_router.include_router(watch.router)
api_router.include_router(organize.router)
api_router.include_router(identify.router)
api_router.include_router(transfer.router)
api_router.include_router(activity.router)
api_router.include_router(admin.router)
