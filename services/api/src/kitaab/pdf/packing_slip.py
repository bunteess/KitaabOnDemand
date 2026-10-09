"""Packing slip PDF (A5) for the vendor and courier (docs/design/screens.md 2.3)."""

import io

from reportlab.graphics.barcode import code128
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from kitaab.domain.enums import PaymentMethod, PaymentStatus
from kitaab.models import Order
from kitaab.money import format_pkr


def _label(value: object | None) -> str:
    return str(value).replace("_", " ").title() if value else "-"


def render_packing_slip(order: Order, courier_name: str | None = None) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A5, pageCompression=1)
    pdf.setTitle(f"Packing slip {order.code}")
    pdf.setAuthor("KitaabOnDemand")
    width, height = A5
    left = 12 * mm
    y = height - 16 * mm

    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(left, y, order.code)
    code128.Code128(order.code, barHeight=12 * mm, barWidth=0.4 * mm).drawOn(
        pdf, width - 75 * mm, y - 6 * mm
    )
    y -= 14 * mm

    def line(label: str, value: str, size: int = 11, bold: bool = False) -> None:
        nonlocal y
        pdf.setFont("Helvetica", 8)
        pdf.drawString(left, y, label.upper())
        y -= 4.5 * mm
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        for part in _wrap(value, 60 if size <= 11 else 40):
            pdf.drawString(left, y, part)
            y -= (size * 0.45) * mm
        y -= 2 * mm

    line("Recipient", order.ship_recipient_name or "-", 13, bold=True)
    line("Phone", order.ship_recipient_phone_e164 or "-")
    line(
        "Address",
        f"{order.ship_street_address or ''}, {order.ship_area or ''}, {order.ship_city_name}",
    )
    line("Nearest landmark", order.ship_landmark or "-", bold=True)
    line("City", order.ship_city_name, 13, bold=True)
    spec = f"{order.copies} cop{'y' if order.copies == 1 else 'ies'}"
    if order.pages:
        spec += f" · {order.pages} pages"
    spec += f" · {_label(order.paper)} · {_label(order.binding)}"
    line("Contents", (order.book_title + " · " if order.book_title else "") + spec)

    if order.cn_number:
        line("Courier", f"{courier_name or order.courier_code or ''}  CN {order.cn_number}")
        code128.Code128(order.cn_number, barHeight=12 * mm, barWidth=0.4 * mm).drawOn(
            pdf, left, y - 10 * mm
        )
        y -= 16 * mm

    is_cod = (
        order.payment_method == PaymentMethod.COD and order.payment_status != PaymentStatus.REFUNDED
    )
    pdf.setFont("Helvetica", 9)
    pdf.drawString(left, 30 * mm, "COLLECT ON DELIVERY" if is_cod else "PAYMENT")
    pdf.setFont("Helvetica-Bold", 26)
    pdf.drawString(
        left, 18 * mm, format_pkr(order.total_paisa or 0) if is_cod else "PAID - collect nothing"
    )
    pdf.setFont("Helvetica", 7)
    pdf.drawString(left, 8 * mm, "KitaabOnDemand")
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _wrap(text: str, width: int) -> list[str]:
    words, lines, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width and current:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return lines or ["-"]
