from fastapi import Depends, Request, status

from kitaab.api.routing import api_router
from kitaab.api.v1.presenters import me_out
from kitaab.domain import auth as auth_domain
from kitaab.domain.context import Ctx
from kitaab.schemas.auth import (
    GoogleSignIn,
    OtpRequest,
    OtpRequested,
    OtpVerify,
    RefreshRequest,
    StaffLogin,
    TokenPair,
)
from kitaab.security.deps import client_ip, public_ctx

router = api_router(prefix="/auth", tags=["auth"])


def _pair(ctx: Ctx, tokens: auth_domain.Tokens) -> TokenPair:
    ctx.session.commit()
    return TokenPair(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user=me_out(ctx, tokens.user),
    )


@router.post("/otp/request", status_code=status.HTTP_202_ACCEPTED)
def request_otp(body: OtpRequest, request: Request, ctx: Ctx = Depends(public_ctx)) -> OtpRequested:
    """Send a 6-digit sign-in code by SMS."""
    sent = auth_domain.request_otp(ctx, body.phone, client_ip(request))
    ctx.session.commit()
    return OtpRequested(
        phone_e164=sent.phone_e164,
        expires_in_seconds=sent.expires_in_seconds,
        resend_after_seconds=sent.resend_after_seconds,
    )


@router.post("/otp/verify")
def verify_otp(body: OtpVerify, request: Request, ctx: Ctx = Depends(public_ctx)) -> TokenPair:
    """Exchange a phone and code for tokens. Creates the customer on first sign-in."""
    phone = auth_domain.verify_otp(ctx, body.phone, body.code, client_ip(request))
    user = auth_domain.customer_for_phone(ctx, phone)
    return _pair(ctx, auth_domain.issue_tokens(ctx, user))


@router.post("/google")
def google_sign_in(body: GoogleSignIn, ctx: Ctx = Depends(public_ctx)) -> TokenPair:
    """Sign in with a Google ID token. The customer must verify a phone before ordering."""
    user = auth_domain.sign_in_with_google(ctx, body.id_token)
    return _pair(ctx, auth_domain.issue_tokens(ctx, user))


@router.post("/refresh")
def refresh_tokens(body: RefreshRequest, ctx: Ctx = Depends(public_ctx)) -> TokenPair:
    """Rotate the refresh token. Reusing an old token revokes the whole session family."""
    return _pair(ctx, auth_domain.refresh_tokens(ctx, body.refresh_token))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body: RefreshRequest, ctx: Ctx = Depends(public_ctx)) -> None:
    auth_domain.logout(ctx, body.refresh_token)
    ctx.session.commit()


@router.post("/staff/login")
def staff_login(body: StaffLogin, request: Request, ctx: Ctx = Depends(public_ctx)) -> TokenPair:
    """Admin and vendor sign-in. Admins must also send a TOTP code."""
    user = auth_domain.staff_login(
        ctx, body.email, body.password, body.totp_code, client_ip(request)
    )
    return _pair(ctx, auth_domain.issue_tokens(ctx, user))
