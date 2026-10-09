import uuid

from fastapi import APIRouter, status

from kitaab.problems import not_implemented
from kitaab.schemas.auth import OtpRequest, OtpRequested, OtpVerify
from kitaab.schemas.catalog import AddressIn, AddressOut
from kitaab.schemas.me import (
    AccountDeletion,
    AccountDeletionResult,
    DeviceRegister,
    DeviceUnregister,
    MeOut,
    MeUpdate,
    TermsAccept,
)

router = APIRouter(prefix="/me", tags=["me"])


@router.get("")
def get_me() -> MeOut:
    raise not_implemented()


@router.patch("")
def update_me(body: MeUpdate) -> MeOut:
    raise not_implemented()


@router.post("/phone/request", status_code=status.HTTP_202_ACCEPTED)
def request_phone_link(body: OtpRequest) -> OtpRequested:
    """Send a code to add a phone number to a Google account."""
    raise not_implemented()


@router.post("/phone/verify")
def verify_phone_link(body: OtpVerify) -> MeOut:
    raise not_implemented()


@router.post("/terms")
def accept_terms(body: TermsAccept) -> MeOut:
    """Record acceptance of the current terms and privacy policy."""
    raise not_implemented()


@router.post("/delete")
def delete_account(body: AccountDeletion) -> AccountDeletionResult:
    """Delete the account and personal data now. Financial records are kept anonymised."""
    raise not_implemented()


@router.post("/devices", status_code=status.HTTP_204_NO_CONTENT)
def register_device(body: DeviceRegister) -> None:
    raise not_implemented()


@router.post("/devices/unregister", status_code=status.HTTP_204_NO_CONTENT)
def unregister_device(body: DeviceUnregister) -> None:
    raise not_implemented()


@router.get("/addresses")
def list_addresses() -> list[AddressOut]:
    raise not_implemented()


@router.post("/addresses", status_code=status.HTTP_201_CREATED)
def create_address(body: AddressIn) -> AddressOut:
    raise not_implemented()


@router.put("/addresses/{address_id}")
def update_address(address_id: uuid.UUID, body: AddressIn) -> AddressOut:
    raise not_implemented()


@router.delete("/addresses/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(address_id: uuid.UUID) -> None:
    raise not_implemented()
