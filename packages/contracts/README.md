# Contracts

Files shared between the backend and the clients. Do not edit `openapi.json`
by hand.

| File | Source | Consumers |
|---|---|---|
| `openapi.json` | Generated from FastAPI by `make contracts` | Web client types (`apps/web/src/api/schema.d.ts`), Dart client contract test |
| `pricing_vectors.json` | Hand-written cases | `services/api/tests/test_pricing_vectors.py`, `apps/mobile/test/pricing_vectors_test.dart` |

`make contracts-check` (part of `make verify`) fails when `openapi.json` or
the generated web types are out of date.

## Pricing vectors

Each case gives a pricing config, an input and either the expected breakdown
or the expected error code. Both calculators must produce identical results.
Add a case whenever the pricing rules change.
