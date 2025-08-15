"""API routes for Water Accounting Service"""

from fastapi import APIRouter
from .accounting import router as accounting_router
from .delivery import router as delivery_router
from .efficiency import router as efficiency_router
from .deficit import router as deficit_router
from .reconciliation import router as reconciliation_router

router = APIRouter()

# Include sub-routers
router.include_router(accounting_router, prefix="/accounting", tags=["accounting"])
router.include_router(delivery_router, prefix="/delivery", tags=["delivery"])
router.include_router(efficiency_router, prefix="/efficiency", tags=["efficiency"])
router.include_router(deficit_router, prefix="/deficits", tags=["deficits"])
router.include_router(reconciliation_router, prefix="/reconciliation", tags=["reconciliation"])