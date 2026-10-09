import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Link, useParams } from "react-router";
import { api, download, errorMessage, unwrap, type Schemas } from "../../api/client";
import { BINDINGS, PAPERS, PriceBreakdown, StatusBadge } from "../../components/domain";
import {
  Button,
  Card,
  ErrorBox,
  KeyValue,
  Select,
  Spinner,
  TextArea,
  TextInput,
} from "../../components/ui";
import { formatDateTime, formatPkr, humanize, parseRupees } from "../../lib/format";

type Order = Schemas["AdminOrderDetail"];
type ActionFn = () => Promise<Order>;

const p = (id: string) => ({ params: { path: { order_id: id } } });

export function OrderDetailPage() {
  const { orderId = "" } = useParams();
  const queryClient = useQueryClient();
  const order = useQuery({
    queryKey: ["admin", "order", orderId],
    queryFn: () => unwrap(api.GET("/api/v1/admin/orders/{order_id}", p(orderId))),
  });
  const action = useMutation({
    mutationFn: (fn: ActionFn) => fn(),
    onSuccess: (updated) => {
      queryClient.setQueryData(["admin", "order", orderId], updated);
      void queryClient.invalidateQueries({ queryKey: ["admin", "orders"] });
    },
  });

  if (order.isPending) return <Spinner />;
  if (order.isError)
    return <ErrorBox message={errorMessage(order.error)} onRetry={() => void order.refetch()} />;
  const o = order.data;
  const run = (fn: ActionFn) => action.mutate(fn);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Link to="/admin" className="text-sm text-brand-800 hover:underline">
          ← Orders
        </Link>
        <h1 className="font-mono text-xl font-semibold">{o.code}</h1>
        <StatusBadge status={o.status} />
        <span className="text-sm text-slate-600">{o.type}</span>
        {o.customer.is_review_account && (
          <span className="rounded bg-amber-200 px-2 text-xs font-semibold">
            TEST — store review account, do not fulfil
          </span>
        )}
      </div>
      {action.isError && <ErrorBox message={errorMessage(action.error)} />}
      <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
        <div className="space-y-4">
          <ItemCard order={o} />
          {o.price && (
            <Card title="Price">
              <PriceBreakdown price={o.price} />
            </Card>
          )}
          {o.quotes.length > 0 && <QuotesCard quotes={o.quotes} />}
          <Card title="Customer and delivery">
            <KeyValue
              items={[
                ["Customer", o.customer.full_name],
                ["Phone", o.customer.phone_e164],
                ["Recipient", `${o.shipping.recipient_name}, ${o.shipping.recipient_phone_e164}`],
                [
                  "Address",
                  `${o.shipping.street_address}, ${o.shipping.area}, ${o.shipping.city_name}`,
                ],
                ["Landmark", o.shipping.landmark],
              ]}
            />
          </Card>
          <Card title="Payment">
            {o.payments.length === 0 ? (
              <p className="text-sm text-slate-500">No payment yet.</p>
            ) : (
              <ul className="space-y-1 text-sm">
                {o.payments.map((pay) => (
                  <li key={pay.id}>
                    {pay.method} · {pay.status} · {formatPkr(pay.amount_paisa)}{" "}
                    {pay.paid_at && `· paid ${formatDateTime(pay.paid_at)}`}
                  </li>
                ))}
              </ul>
            )}
            {o.refunds.length > 0 && (
              <ul className="mt-2 space-y-1 text-sm">
                {o.refunds.map((r) => (
                  <li key={r.id}>
                    Refund {formatPkr(r.amount_paisa)} · {r.status} · {r.reason}
                  </li>
                ))}
              </ul>
            )}
          </Card>
          {o.tracking && (
            <Card title="Shipment">
              <KeyValue
                items={[
                  ["Courier", o.tracking.courier_name],
                  ["CN", <span className="font-mono">{o.tracking.cn_number}</span>],
                  ["Dispatched", formatDateTime(o.tracking.dispatched_at)],
                  ["Last status", o.tracking.last_status],
                  [
                    "Tracking",
                    o.tracking.tracking_url ? (
                      <a
                        className="text-brand-800 underline"
                        href={o.tracking.tracking_url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open
                      </a>
                    ) : (
                      "—"
                    ),
                  ],
                ]}
              />
            </Card>
          )}
          <HistoryCard history={o.history} />
        </div>
        <div className="space-y-4">
          <ActionsPanel order={o} busy={action.isPending} run={run} />
        </div>
      </div>
    </div>
  );
}

function ItemCard({ order: o }: { order: Order }) {
  const upload = o.admin_upload;
  return (
    <Card title={o.type === "PRINT" ? "File and options" : "Book request"}>
      <KeyValue
        items={[
          ...(o.book
            ? ([
                ["Title", o.book.title],
                ["Author", o.book.author],
                ["ISBN", o.book.isbn],
                ["Edition", o.book.edition],
                ["Notes", o.book.notes],
                [
                  "Preferences",
                  [o.book.preferred_paper, o.book.preferred_binding]
                    .filter(Boolean)
                    .map((v) => humanize(v!))
                    .join(", ") || "None",
                ],
              ] as [string, ReactNode][])
            : []),
          ...(upload
            ? ([
                ["File", upload.filename],
                ["Size", `${(upload.size_bytes / 1024 / 1024).toFixed(1)} MB`],
                ["Pages (server)", upload.page_count],
                ["Pages (app)", upload.client_page_count],
                ["SHA-256", <span className="font-mono text-xs break-all">{upload.sha256}</span>],
                [
                  "File",
                  upload.file_available
                    ? "Available"
                    : `Purged ${formatDateTime(upload.purged_at)}`,
                ],
              ] as [string, ReactNode][])
            : []),
          [
            "Options",
            [
              o.pages && `${o.pages} pages`,
              o.paper && humanize(o.paper),
              o.binding && humanize(o.binding),
              `${o.copies} copies`,
            ]
              .filter(Boolean)
              .join(" · "),
          ],
          [
            "Vendor",
            o.vendor ? `${o.vendor.name} (cost ${formatPkr(o.vendor_cost_paisa ?? 0)})` : "—",
          ],
          ...(o.rejection_reason
            ? ([["Rejected", o.rejection_reason]] as [string, ReactNode][])
            : []),
          ...(o.cancel_reason ? ([["Cancelled", o.cancel_reason]] as [string, ReactNode][]) : []),
        ]}
      />
    </Card>
  );
}

function QuotesCard({ quotes }: { quotes: Schemas["AdminQuoteOut"][] }) {
  return (
    <Card title="Quotes">
      <ul className="space-y-2 text-sm">
        {quotes.map((q) => (
          <li key={q.id} className="rounded border border-slate-200 p-2">
            <div className="flex justify-between">
              <span>
                {q.pages} pages · {humanize(q.paper)} · {humanize(q.binding)} · {q.copies} copies
              </span>
              <StatusBadge status={q.status} />
            </div>
            <div>
              Goods {formatPkr(q.goods_paisa)} (calculated {formatPkr(q.calculated_goods_paisa)},
              sourcing {formatPkr(q.sourcing_cost_paisa)})
              {q.override_reason && ` · override: ${q.override_reason}`}
            </div>
            <div className="text-slate-500">
              Valid until {formatDateTime(q.valid_until)} · by {q.created_by_name ?? "—"}
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function HistoryCard({ history }: { history: Schemas["StatusHistoryOut"][] }) {
  return (
    <Card title="History">
      <ol className="space-y-1 text-sm">
        {history.map((h, i) => (
          <li key={i}>
            <span className="text-slate-500">{formatDateTime(h.created_at)}</span> ·{" "}
            {h.from_status ? `${humanize(h.from_status)} → ` : ""}
            <strong>{humanize(h.to_status)}</strong> by {h.actor_name ?? humanize(h.actor)}
            {h.reason && ` — ${h.reason}`}
          </li>
        ))}
      </ol>
    </Card>
  );
}

function ActionsPanel({
  order: o,
  busy,
  run,
}: {
  order: Order;
  busy: boolean;
  run: (fn: ActionFn) => void;
}) {
  const has = (a: string) => o.allowed_actions.includes(a);
  const id = o.id;
  const [error, setError] = useState<string | null>(null);

  const openFile = async () => {
    setError(null);
    try {
      const file = await unwrap(api.GET("/api/v1/admin/orders/{order_id}/file-url", p(id)));
      window.open(file.url, "_blank", "noopener");
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <Card title="Actions">
      <div className="space-y-4">
        {error && <ErrorBox message={error} />}
        <div className="flex flex-wrap gap-2">
          {o.admin_upload?.file_available && (
            <Button variant="secondary" onClick={() => void openFile()}>
              Open PDF
            </Button>
          )}
          <Button
            variant="secondary"
            onClick={() =>
              download(
                `/api/v1/admin/orders/${id}/packing-slip`,
                `packing-slip-${o.code}.pdf`,
              ).catch((e) => setError(errorMessage(e)))
            }
          >
            Packing slip
          </Button>
        </div>
        {o.allowed_actions.length === 0 && (
          <p className="text-sm text-slate-500">No actions available in this state.</p>
        )}
        {has("start-verification") && (
          <Button
            busy={busy}
            className="w-full"
            onClick={() =>
              run(() =>
                unwrap(api.POST("/api/v1/admin/orders/{order_id}/start-verification", p(id))),
              )
            }
          >
            Start verification
          </Button>
        )}
        {has("approve") && (
          <ApproveForm
            busy={busy}
            onSubmit={(body) =>
              run(() =>
                unwrap(api.POST("/api/v1/admin/orders/{order_id}/approve", { ...p(id), body })),
              )
            }
          />
        )}
        {has("quote") && (
          <QuoteForm
            orderId={id}
            order={o}
            busy={busy}
            onSubmit={(body) =>
              run(() =>
                unwrap(api.POST("/api/v1/admin/orders/{order_id}/quote", { ...p(id), body })),
              )
            }
          />
        )}
        {has("start-sourcing") && (
          <SourcingForm
            busy={busy}
            onSubmit={(body) =>
              run(() =>
                unwrap(
                  api.POST("/api/v1/admin/orders/{order_id}/start-sourcing", { ...p(id), body }),
                ),
              )
            }
          />
        )}
        {has("start-printing") && (
          <Button
            busy={busy}
            variant="secondary"
            className="w-full"
            onClick={() =>
              run(() => unwrap(api.POST("/api/v1/admin/orders/{order_id}/start-printing", p(id))))
            }
          >
            Mark printing (for vendor)
          </Button>
        )}
        {has("ready-for-dispatch") && (
          <Button
            busy={busy}
            variant="secondary"
            className="w-full"
            onClick={() =>
              run(() =>
                unwrap(api.POST("/api/v1/admin/orders/{order_id}/ready-for-dispatch", p(id))),
              )
            }
          >
            Mark ready for dispatch
          </Button>
        )}
        {has("dispatch") && (
          <DispatchForm
            busy={busy}
            onSubmit={(body) =>
              run(() =>
                unwrap(api.POST("/api/v1/admin/orders/{order_id}/dispatch", { ...p(id), body })),
              )
            }
          />
        )}
        {has("mark-delivered") && (
          <Button
            busy={busy}
            className="w-full"
            onClick={() =>
              run(() => unwrap(api.POST("/api/v1/admin/orders/{order_id}/mark-delivered", p(id))))
            }
          >
            Mark delivered
          </Button>
        )}
        {has("mark-delivery-failed") && (
          <ReasonAction
            label="Mark delivery failed"
            busy={busy}
            onSubmit={(reason) =>
              run(() =>
                unwrap(
                  api.POST("/api/v1/admin/orders/{order_id}/mark-delivery-failed", {
                    ...p(id),
                    body: { reason },
                  }),
                ),
              )
            }
          />
        )}
        {has("reject") && (
          <ReasonAction
            label="Reject"
            danger
            busy={busy}
            onSubmit={(reason) =>
              run(() =>
                unwrap(
                  api.POST("/api/v1/admin/orders/{order_id}/reject", {
                    ...p(id),
                    body: { reason },
                  }),
                ),
              )
            }
          />
        )}
        {has("mark-unavailable") && (
          <ReasonAction
            label="Mark unavailable"
            danger
            busy={busy}
            onSubmit={(reason) =>
              run(() =>
                unwrap(
                  api.POST("/api/v1/admin/orders/{order_id}/mark-unavailable", {
                    ...p(id),
                    body: { reason },
                  }),
                ),
              )
            }
          />
        )}
        {has("cancel") && (
          <ReasonAction
            label="Cancel order"
            danger
            busy={busy}
            onSubmit={(reason) =>
              run(() =>
                unwrap(
                  api.POST("/api/v1/admin/orders/{order_id}/cancel", {
                    ...p(id),
                    body: { reason },
                  }),
                ),
              )
            }
          />
        )}
        {o.payments.some((pay) => pay.status === "PAID") && <RefundForm orderId={id} />}
      </div>
    </Card>
  );
}

function useVendors() {
  return useQuery({
    queryKey: ["admin", "vendors"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/vendors", {})),
  });
}

function MoneyInput({
  label,
  value,
  onChange,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  required?: boolean;
}) {
  const invalid = value !== "" && parseRupees(value) === null;
  return (
    <TextInput
      label={`${label} (Rs.)`}
      inputMode="decimal"
      required={required}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      error={invalid ? "Enter an amount like 1250 or 1250.50" : undefined}
    />
  );
}

function ApproveForm({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (body: Schemas["ApproveAndAssign"]) => void;
}) {
  const vendors = useVendors();
  const [vendorId, setVendorId] = useState("");
  const [cost, setCost] = useState("");
  const costPaisa = parseRupees(cost);
  return (
    <form
      className="space-y-2 rounded-md border border-slate-200 p-3"
      onSubmit={(e) => {
        e.preventDefault();
        if (vendorId && costPaisa !== null)
          onSubmit({ vendor_id: vendorId, vendor_cost_paisa: costPaisa });
      }}
    >
      <p className="text-sm font-medium">Approve and assign</p>
      <Select
        label="Vendor"
        required
        value={vendorId}
        onChange={(e) => setVendorId(e.target.value)}
      >
        <option value="">Choose a vendor</option>
        {vendors.data
          ?.filter((v) => v.is_active)
          .map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
      </Select>
      <MoneyInput label="Agreed vendor cost" required value={cost} onChange={setCost} />
      <Button
        type="submit"
        busy={busy}
        className="w-full"
        disabled={!vendorId || costPaisa === null}
      >
        Approve and assign
      </Button>
    </form>
  );
}

function SourcingForm({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (body: Schemas["StartSourcing"]) => void;
}) {
  const vendors = useVendors();
  const [vendorId, setVendorId] = useState("");
  const [cost, setCost] = useState("");
  return (
    <form
      className="space-y-2 rounded-md border border-slate-200 p-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(
          vendorId ? { vendor_id: vendorId, vendor_cost_paisa: parseRupees(cost) ?? 0 } : {},
        );
      }}
    >
      <p className="text-sm font-medium">Start sourcing</p>
      <Select
        label="Vendor (optional)"
        value={vendorId}
        onChange={(e) => setVendorId(e.target.value)}
      >
        <option value="">In-house</option>
        {vendors.data
          ?.filter((v) => v.is_active)
          .map((v) => (
            <option key={v.id} value={v.id}>
              {v.name}
            </option>
          ))}
      </Select>
      {vendorId && <MoneyInput label="Agreed vendor cost" value={cost} onChange={setCost} />}
      <Button type="submit" busy={busy} className="w-full">
        Start sourcing
      </Button>
    </form>
  );
}

function QuoteForm({
  orderId,
  order,
  busy,
  onSubmit,
}: {
  orderId: string;
  order: Order;
  busy: boolean;
  onSubmit: (body: Schemas["QuoteIn"]) => void;
}) {
  const [pages, setPages] = useState("");
  const [paper, setPaper] = useState<Schemas["Paper"]>(
    order.book?.preferred_paper ?? "LOCAL_WHITE",
  );
  const [binding, setBinding] = useState<Schemas["Binding"]>(
    order.book?.preferred_binding ?? "SOFTCOVER_PAPERBACK",
  );
  const [copies, setCopies] = useState(String(order.copies));
  const [sourcing, setSourcing] = useState("");
  const [override, setOverride] = useState("");
  const [reason, setReason] = useState("");
  const [hours, setHours] = useState("48");
  const [preview, setPreview] = useState<Schemas["QuotePreview"] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const body = (): Schemas["QuoteIn"] | null => {
    const sourcingPaisa = parseRupees(sourcing || "0");
    if (!Number(pages) || !Number(copies) || sourcingPaisa === null) return null;
    const overridePaisa = override ? parseRupees(override) : null;
    return {
      pages: Number(pages),
      paper,
      binding,
      copies: Number(copies),
      sourcing_cost_paisa: sourcingPaisa,
      goods_override_paisa: overridePaisa,
      override_reason: overridePaisa !== null ? reason : null,
      valid_hours: Number(hours) || null,
    };
  };

  const doPreview = async () => {
    const b = body();
    if (!b) return;
    setError(null);
    try {
      setPreview(
        await unwrap(
          api.POST("/api/v1/admin/orders/{order_id}/quote/preview", { ...p(orderId), body: b }),
        ),
      );
    } catch (err) {
      setError(errorMessage(err));
    }
  };

  return (
    <form
      className="space-y-2 rounded-md border border-slate-200 p-3"
      onSubmit={(e) => {
        e.preventDefault();
        const b = body();
        if (b) onSubmit(b);
      }}
    >
      <p className="text-sm font-medium">Send a quote</p>
      {error && <ErrorBox message={error} />}
      <div className="grid grid-cols-2 gap-2">
        <TextInput
          label="Pages"
          inputMode="numeric"
          required
          value={pages}
          onChange={(e) => setPages(e.target.value)}
        />
        <TextInput
          label="Copies"
          inputMode="numeric"
          required
          value={copies}
          onChange={(e) => setCopies(e.target.value)}
        />
      </div>
      <Select
        label="Paper"
        value={paper}
        onChange={(e) => setPaper(e.target.value as Schemas["Paper"])}
      >
        {PAPERS.map((v) => (
          <option key={v} value={v}>
            {humanize(v)}
          </option>
        ))}
      </Select>
      <Select
        label="Binding"
        value={binding}
        onChange={(e) => setBinding(e.target.value as Schemas["Binding"])}
      >
        {BINDINGS.map((v) => (
          <option key={v} value={v}>
            {humanize(v)}
          </option>
        ))}
      </Select>
      <MoneyInput label="Sourcing cost" value={sourcing} onChange={setSourcing} />
      <MoneyInput label="Override goods price (optional)" value={override} onChange={setOverride} />
      {override && (
        <TextArea
          label="Override reason"
          required
          minLength={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
      )}
      <TextInput
        label="Valid for (hours)"
        inputMode="numeric"
        value={hours}
        onChange={(e) => setHours(e.target.value)}
      />
      <Button variant="secondary" className="w-full" onClick={() => void doPreview()}>
        Preview price
      </Button>
      {preview && (
        <div className="rounded bg-slate-50 p-2" data-testid="quote-preview">
          <PriceBreakdown price={preview.breakdown} />
          <p className="mt-1 text-sm">
            Online: <strong>{formatPkr(preview.total_if_digital_paisa)}</strong> · COD:{" "}
            <strong>{formatPkr(preview.total_if_cod_paisa)}</strong>
          </p>
        </div>
      )}
      <Button type="submit" busy={busy} className="w-full">
        Send quote
      </Button>
    </form>
  );
}

function DispatchForm({
  busy,
  onSubmit,
}: {
  busy: boolean;
  onSubmit: (body: Schemas["DispatchIn"]) => void;
}) {
  const couriers = useQuery({
    queryKey: ["admin", "couriers"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/couriers", {})),
  });
  const [courier, setCourier] = useState("");
  const [cn, setCn] = useState("");
  const [url, setUrl] = useState("");
  const selected = couriers.data?.find((c) => c.code === courier);
  return (
    <form
      className="space-y-2 rounded-md border border-slate-200 p-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit({ courier_code: courier, cn_number: cn || null, tracking_url: url || null });
      }}
    >
      <p className="text-sm font-medium">Dispatch</p>
      <Select label="Courier" required value={courier} onChange={(e) => setCourier(e.target.value)}>
        <option value="">Choose a courier</option>
        {couriers.data?.map((c) => (
          <option key={c.code} value={c.code}>
            {c.name}
          </option>
        ))}
      </Select>
      {selected && (
        <>
          <TextInput
            label={selected.has_api ? "CN number (only if the courier API is down)" : "CN number"}
            required={!selected.has_api}
            value={cn}
            onChange={(e) => setCn(e.target.value)}
          />
          {(cn || !selected.has_api) && (
            <TextInput
              label="Tracking link (optional)"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          )}
        </>
      )}
      <Button type="submit" busy={busy} className="w-full" disabled={!courier}>
        Book courier and dispatch
      </Button>
    </form>
  );
}

function ReasonAction({
  label,
  danger = false,
  busy,
  onSubmit,
}: {
  label: string;
  danger?: boolean;
  busy: boolean;
  onSubmit: (reason: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  if (!open) {
    return (
      <Button
        variant="secondary"
        className={`w-full ${danger ? "text-red-800" : ""}`}
        onClick={() => setOpen(true)}
      >
        {label}
      </Button>
    );
  }
  return (
    <form
      className="space-y-2 rounded-md border border-slate-200 p-3"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit(reason);
      }}
    >
      <TextArea
        label={`${label}: reason`}
        required
        minLength={3}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
      <div className="flex gap-2">
        <Button
          type="submit"
          variant={danger ? "danger" : "primary"}
          busy={busy}
          disabled={reason.trim().length < 3}
        >
          {label}
        </Button>
        <Button variant="ghost" onClick={() => setOpen(false)}>
          Back
        </Button>
      </div>
    </form>
  );
}

function RefundForm({ orderId }: { orderId: string }) {
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState("");
  const [reason, setReason] = useState("");
  const refund = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/admin/orders/{order_id}/refunds", {
          ...p(orderId),
          body: { amount_paisa: parseRupees(amount) ?? 0, reason },
        }),
      ),
    onSuccess: () => {
      setAmount("");
      setReason("");
      void queryClient.invalidateQueries({ queryKey: ["admin", "order", orderId] });
    },
  });
  return (
    <details className="rounded-md border border-slate-200 p-3">
      <summary className="cursor-pointer text-sm font-medium">Create a manual refund</summary>
      <form
        className="mt-2 space-y-2"
        onSubmit={(e) => {
          e.preventDefault();
          refund.mutate();
        }}
      >
        {refund.isError && <ErrorBox message={errorMessage(refund.error)} />}
        <MoneyInput label="Amount" required value={amount} onChange={setAmount} />
        <TextArea
          label="Reason"
          required
          minLength={3}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
        />
        <Button
          type="submit"
          busy={refund.isPending}
          disabled={!parseRupees(amount) || reason.trim().length < 3}
        >
          Create refund
        </Button>
      </form>
    </details>
  );
}
