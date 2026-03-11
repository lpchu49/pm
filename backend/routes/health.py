from fastapi import APIRouter

from models import HealthResponse

router = APIRouter()


@router.get("/api/health")
def health() -> HealthResponse:
  return HealthResponse(status="ok", service="pm-backend")
