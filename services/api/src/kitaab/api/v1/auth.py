from fastapi import APIRouter, status

from kitaab.problems import not_implemented
from kitaab.schemas.auth import (
    GoogleSignIn,
    OtpRequest,
    OtpRequested,
    OtpVerify,
    RefreshRequest,
    StaffLogin,
    TokenPair,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/otp/request", status_code=status.HTTP_202_ACCEPTED)
def request_otp(body: OtpRequest) -> OtpRequested:
    """Send a 6-digit sign-in code by SMS."""
    raise not_implemented()


@router.post("/otp/verify")
def verify_otp(body: OtpVerify) -> TokenPair:
    """Exchange a phone and code for tokens. Creates the customer on first sign-in."""
    raise not_implemented()


@router.post("/google")
def google_sign_in(body: GoogleSignIn) -> TokenPair:
    """Sign in with a Google ID token. The customer must verify a phone before ordering."""
    raise not_implemented()


@router.post("/refresh")
def refresh_tokens(body: RefreshRequest) -> TokenPair:
    """Rotate the refresh token. Reusing an old token revokes the whole session family."""
    raise not_implemented()


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest) -> None:
    raise not_implemented()


@router.post("/staff/login")
def staff_login(body: StaffLogin) -> TokenPair:
    """Admin and vendor sign-in. Admins must also send a TOTP code."""
    raise not_implemented()
