from fastapi import APIRouter
from app.api.routes import auth, society, wing, flat, user, notifications
from app.api.routes.role  import router as role_router
from app.api.routes.floor import router as floor_router
from app.api.routes.vehicle           import router as vehicle_router
from app.api.routes.workload          import router as workload_router
from app.api.routes.occupancy         import router as occupancy_router
from app.api.routes.payroll_readiness import router as payroll_router
from app.modules.visitor.routes.visitor     import router as visitor_router
from app.modules.complaint.routes.complaint import router as complaint_router
from app.modules.amenity.routes.amenity     import router as amenity_router
from app.modules.staff.routes.staff         import router as staff_router
from app.modules.staff.routes.handover      import router as handover_router
from app.modules.inventory.routes.inventory import router as inventory_router
from app.modules.parking.routes.parking     import router as parking_router
from app.modules.notice.routes.notice       import router as notice_router
from app.modules.billing.routes.billing     import router as billing_router
from app.modules.vendor.routes.vendor               import router as vendor_router
from app.modules.onboarding.routes.onboarding       import router as onboarding_router
from app.modules.platform_admin.routes.platform_admin import router as platform_admin_router

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(society.router)
api_router.include_router(wing.router)
api_router.include_router(flat.router)
api_router.include_router(user.router)
api_router.include_router(role_router)
api_router.include_router(floor_router)
api_router.include_router(notifications.router)
api_router.include_router(vehicle_router)
api_router.include_router(workload_router)
api_router.include_router(occupancy_router)
api_router.include_router(payroll_router)
api_router.include_router(visitor_router)
api_router.include_router(complaint_router)
api_router.include_router(amenity_router)
api_router.include_router(staff_router)
api_router.include_router(handover_router)
api_router.include_router(inventory_router)
api_router.include_router(parking_router)
api_router.include_router(notice_router)
api_router.include_router(billing_router)
api_router.include_router(vendor_router)
api_router.include_router(onboarding_router)
api_router.include_router(platform_admin_router)
