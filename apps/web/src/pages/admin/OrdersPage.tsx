import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { api, errorMessage, unwrap, type Schemas } from "../../api/client";
import { StatusBadge } from "../../components/domain";
import { Pagination, Table, type Column } from "../../components/Table";
import { Button, ErrorBox, PageHeader, Select, Spinner, TextInput } from "../../components/ui";
import { formatDateTime, formatPkr } from "../../lib/format";

type Status = Schemas["OrderStatus"];

/** Quick tabs for the review station's daily work. */
const TABS: { label: string; type?: Schemas["OrderType"]; status: Status[] }[] = [
  { label: "To verify", type: "PRINT", status: ["PLACED", "VERIFYING"] },
  { label: "To quote", type: "SOURCE", status: ["REQUESTED"] },
  { label: "To source", type: "SOURCE", status: ["ACCEPTED", "SOURCING"] },
  { label: "Printing", type: "PRINT", status: ["ASSIGNED", "IN_PRINT"] },
  { label: "Ready to dispatch", status: ["READY_FOR_DISPATCH"] },
  { label: "Out for delivery", status: ["DISPATCHED"] },
  { label: "All", status: [] },
];
const ALL_TAB = TABS.length - 1;

const columns: Column<Schemas["AdminOrderSummary"]>[] = [
  {
    header: "Order",
    cell: (o) => (
      <div>
        <div className="font-mono font-medium">{o.code}</div>
        {o.is_review_account && (
          <span className="rounded bg-amber-200 px-1 text-xs font-semibold">TEST</span>
        )}
      </div>
    ),
  },
  { header: "Type", cell: (o) => o.type },
  { header: "Status", cell: (o) => <StatusBadge status={o.status} /> },
  { header: "Item", cell: (o) => <span className="line-clamp-2 max-w-60">{o.title}</span> },
  {
    header: "Customer",
    cell: (o) => (
      <div>
        {o.customer_name ?? "—"}
        <div className="text-xs text-slate-500">{o.customer_phone_masked}</div>
      </div>
    ),
  },
  { header: "City", cell: (o) => o.city_name },
  { header: "Copies", cell: (o) => o.copies, className: "text-right" },
  {
    header: "Total",
    cell: (o) => (o.total_paisa == null ? "—" : formatPkr(o.total_paisa)),
    className: "text-right whitespace-nowrap",
  },
  {
    header: "Payment",
    cell: (o) => (o.payment_method ? `${o.payment_method} · ${o.payment_status}` : "—"),
  },
  { header: "Vendor", cell: (o) => o.vendor_name ?? "—" },
  {
    header: "Created",
    cell: (o) => <span className="whitespace-nowrap">{formatDateTime(o.created_at)}</span>,
  },
];

export function OrdersPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tabIndex = Number(params.get("tab") ?? 0);
  const tab = TABS[tabIndex] ?? TABS[0]!;
  const page = Number(params.get("page") ?? 1);
  const q = params.get("q") ?? "";
  const [search, setSearch] = useState(q);
  const typeFilter = (params.get("type") as Schemas["OrderType"] | null) ?? tab.type;

  const orders = useQuery({
    queryKey: ["admin", "orders", tabIndex, typeFilter, q, page],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/orders", {
          params: {
            query: {
              type: typeFilter ?? null,
              status: tab.status.length ? tab.status : null,
              q: q || null,
              page,
              page_size: 25,
            },
          },
        }),
      ),
  });

  const set = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v === null || v === "") next.delete(k);
      else next.set(k, v);
    }
    setParams(next);
  };

  return (
    <div>
      <PageHeader title="Orders" />
      <div role="tablist" className="mb-4 flex flex-wrap gap-2">
        {TABS.map((t, i) => (
          <button
            key={t.label}
            role="tab"
            aria-selected={i === tabIndex}
            className={`rounded-full px-3 py-1 text-sm ${i === tabIndex ? "bg-brand-700 text-white" : "bg-white text-slate-700 ring-1 ring-slate-300"}`}
            onClick={() => set({ tab: String(i), page: null, type: null })}
          >
            {t.label}
          </button>
        ))}
      </div>
      <form
        className="mb-4 grid gap-3 sm:grid-cols-[1fr_12rem_auto] sm:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          // A search looks through every status, not just the open tab.
          set(search.trim() ? { q: search, page: null, tab: String(ALL_TAB) } : { q: null });
        }}
      >
        <TextInput
          label="Search"
          placeholder="Order code, phone or name"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select
          label="Type"
          value={typeFilter ?? ""}
          onChange={(e) => set({ type: e.target.value || null, page: null })}
        >
          <option value="">Any</option>
          <option value="PRINT">PRINT</option>
          <option value="SOURCE">SOURCE</option>
        </Select>
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>
      {orders.isPending && <Spinner />}
      {orders.isError && (
        <ErrorBox message={errorMessage(orders.error)} onRetry={() => void orders.refetch()} />
      )}
      {orders.data && (
        <>
          <Table
            columns={columns}
            rows={orders.data.items}
            rowKey={(o) => o.id}
            onRowClick={(o) => navigate(`/admin/orders/${o.id}`)}
            empty="No orders match these filters"
          />
          <Pagination
            page={orders.data.page}
            pageSize={orders.data.page_size}
            total={orders.data.total}
            onPage={(p) => set({ page: String(p) })}
          />
        </>
      )}
    </div>
  );
}
