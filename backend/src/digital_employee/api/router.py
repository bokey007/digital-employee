"""API router aggregator — mounts all sub-routers."""

from fastapi import APIRouter

from digital_employee.api.chat import router as chat_router
from digital_employee.api.dashboard import router as dashboard_router
from digital_employee.api.leads import router as leads_router
from digital_employee.api.newsletters import router as newsletters_router

api_router = APIRouter()
api_router.include_router(newsletters_router)
api_router.include_router(dashboard_router)
api_router.include_router(chat_router)
api_router.include_router(leads_router)
