"""Hosted pages of the mock payment gateway and mock courier. Mounted only
when those mock providers are enabled (never in production)."""

import html
from typing import Literal

from fastapi import APIRouter, Depends, Form
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from kitaab.container import Services
from kitaab.models import Order, Payment
from kitaab.money import format_pkr
from kitaab.providers.payment import MockPaymentProvider
from kitaab.security.deps import get_services

router = APIRouter(prefix="/mock", include_in_schema=False)

_PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title><style>body{{font-family:system-ui,sans-serif;max-width:28rem;margin:2rem auto;padding:0 1rem}}
button{{font-size:1rem;padding:.8rem 1.2rem;margin:.3rem 0;width:100%;border-radius:.5rem;border:0;cursor:pointer}}
.pay{{background:#0f5c4d;color:#fff}}.fail{{background:#eee}}.note{{color:#666;font-size:.85rem}}</style></head>
<body>{body}</body></html>"""


def _page(title: str, body: str) -> HTMLResponse:
    return HTMLResponse(_PAGE.format(title=html.escape(title), body=body))


def _payment(services: Services, ref: str) -> tuple[Payment, Order] | None:
    with services.session() as session:
        row = session.execute(
            select(Payment, Order)
            .join(Order, Order.id == Payment.order_id)
            .where(Payment.provider_ref == ref)
        ).first()
        return (row[0], row[1]) if row else None


@router.get("/payments/{ref}")
def checkout_page(ref: str, services: Services = Depends(get_services)) -> HTMLResponse:
    found = _payment(services, ref)
    if found is None:
        return _page("Not found", "<p>Unknown payment.</p>")
    payment, order = found
    return _page(
        "Mock checkout",
        f"""
<h1>Mock payment gateway</h1>
<p>Order <strong>{html.escape(order.code)}</strong><br>Amount <strong>{html.escape(format_pkr(payment.amount_paisa))}</strong>
<br>Method {html.escape(payment.method.value)}</p>
<form method="post" action="/mock/payments/{html.escape(ref)}/complete">
<button class="pay" name="outcome" value="PAID">Pay</button>
<button class="fail" name="outcome" value="FAILED">Decline</button></form>
<p class="note">Development only. No money moves.</p>""",
    )


@router.post("/payments/{ref}/complete")
def complete_checkout(
    ref: str,
    outcome: Literal["PAID", "FAILED"] = Form(...),
    services: Services = Depends(get_services),
) -> HTMLResponse:
    provider = services.payments.get("mock")
    found = _payment(services, ref)
    if not isinstance(provider, MockPaymentProvider) or found is None:
        return _page("Not found", "<p>Unknown payment.</p>")
    payment, order = found
    body, headers = provider.build_webhook(ref, outcome, payment.amount_paisa)
    services.tasks.enqueue(
        "deliver_webhook",
        path="/api/v1/webhooks/payments/mock",
        body=body.decode(),
        headers=headers,
    )
    link = f"kitaab://app/payment-result?order={order.id}"
    message = "Payment received." if outcome == "PAID" else "Payment declined."
    return _page(
        "Done", f'<h1>{message}</h1><p><a href="{html.escape(link)}">Return to the app</a></p>'
    )


@router.get("/couriers/track/{cn}")
def tracking_page(cn: str, services: Services = Depends(get_services)) -> HTMLResponse:
    courier = services.couriers.get("mock")
    events = courier.fetch_events(cn) if courier else []
    rows = (
        "".join(f"<li>{html.escape(e.description or e.state)}</li>" for e in events)
        or "<li>No updates yet</li>"
    )
    return _page(
        f"Tracking {cn}",
        f"<h1>Mock Courier</h1><p>Consignment {html.escape(cn)}</p><ol>{rows}</ol>",
    )
