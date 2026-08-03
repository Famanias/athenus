from fastapi import APIRouter, Depends
from app.application.services.system_reset_service import SystemResetService

router = APIRouter()

# Global reset service instance
system_reset_service = SystemResetService()

def get_system_reset_service() -> SystemResetService:
    return system_reset_service

@router.post("/system/clear-data")
async def clear_all_application_data(
    service: SystemResetService = Depends(get_system_reset_service)
):
    """Factory reset endpoint: purges SQLite tables, Qdrant vectors, disk upload files, and resets default workspace."""
    return await service.perform_factory_reset()
