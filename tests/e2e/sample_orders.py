"""Fresh orders to work through by hand in the portal (make sample-orders).

Signs up a customer the way the app does, then places a cash-on-delivery print
order and requests a book. Both are left at their first step, so an admin and
the vendor can take them the rest of the way (docs/LOCAL_TESTING.md).
"""

import httpx2
import stack


def main() -> None:
    with httpx2.Client(base_url=stack.BASE_URL, timeout=120) as client:
        stack.ok(client.get("/healthz"))
        customer = stack.customer(client)

        uploaded = stack.upload(customer, stack.pdf_of_size(pages=12, size_bytes=200_000))
        options = {"paper": "LOCAL_WHITE", "binding": "SOFTCOVER_PAPERBACK", "copies": 1}
        price = stack.ok(
            client.post(
                "/api/v1/pricing/quote",
                json={
                    **options,
                    "pages": uploaded["page_count"],
                    "city_id": customer.extra["city_id"],
                    "payment_method": "COD",
                },
            )
        )
        printed = customer.post(
            "/api/v1/orders/print",
            {
                **options,
                "upload_id": uploaded["id"],
                "address_id": customer.extra["address_id"],
                "payment_method": "COD",
                "expected_total_paisa": price["total_paisa"],
            },
        )
        book = customer.post(
            "/api/v1/orders/source",
            {
                "book_title": "Peer-e-Kamil",
                "author": "Umera Ahmed",
                "copies": 1,
                "address_id": customer.extra["address_id"],
            },
        )

    print(f"Customer {customer.extra['phone']}")  # noqa: T201
    print(f"Print order {printed['code']}: {printed['status']} (portal: To verify)")  # noqa: T201
    print(f"Book request {book['code']}: {book['status']} (portal: To quote)")  # noqa: T201


if __name__ == "__main__":
    main()
