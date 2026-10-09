import uuid

from fastapi import APIRouter, Query, status

from kitaab.problems import not_implemented
from kitaab.schemas.admin import (
    CustomerDetail,
    CustomerPage,
    StaffUserCreate,
    StaffUserCreated,
    StaffUserOut,
    StaffUserUpdate,
    VendorIn,
    VendorOut,
)

router = APIRouter(prefix="/admin", tags=["admin: people"])


@router.get("/vendors")
def admin_list_vendors(include_inactive: bool = False) -> list[VendorOut]:
    raise not_implemented()


@router.post("/vendors", status_code=status.HTTP_201_CREATED)
def admin_create_vendor(body: VendorIn) -> VendorOut:
    raise not_implemented()


@router.put("/vendors/{vendor_id}")
def admin_update_vendor(vendor_id: uuid.UUID, body: VendorIn) -> VendorOut:
    raise not_implemented()


@router.get("/vendors/{vendor_id}/users")
def admin_list_vendor_users(vendor_id: uuid.UUID) -> list[StaffUserOut]:
    raise not_implemented()


@router.post("/vendors/{vendor_id}/users", status_code=status.HTTP_201_CREATED)
def admin_create_vendor_user(vendor_id: uuid.UUID, body: StaffUserCreate) -> StaffUserCreated:
    raise not_implemented()


@router.get("/staff")
def admin_list_admins() -> list[StaffUserOut]:
    raise not_implemented()


@router.post("/staff", status_code=status.HTTP_201_CREATED)
def admin_create_admin(body: StaffUserCreate) -> StaffUserCreated:
    """Create another admin. The response includes a TOTP setup link, shown once."""
    raise not_implemented()


@router.patch("/staff/{user_id}")
def admin_update_staff_user(user_id: uuid.UUID, body: StaffUserUpdate) -> StaffUserOut:
    """Deactivate, reactivate or unlock an admin or vendor user."""
    raise not_implemented()


@router.get("/customers")
def admin_list_customers(
    q: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> CustomerPage:
    """Read-only support view."""
    raise not_implemented()


@router.get("/customers/{user_id}")
def admin_get_customer(user_id: uuid.UUID) -> CustomerDetail:
    raise not_implemented()
