import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router";
import { api, errorMessage, unwrap, type Schemas } from "../../api/client";
import { StatusBadge } from "../../components/domain";
import { Pagination, Table } from "../../components/Table";
import { ErrorBox, PageHeader, Select, Spinner } from "../../components/ui";
import { formatDateTime, formatPkr, humanize } from "../../lib/format";

const FILTERS: { label: string; status: Schemas["OrderStatus"][] }[] = [
  { label: "To do", status: ["ASSIGNED", "IN_PRINT", "SOURCING"] },
  { label: "Ready for dispatch", status: ["READY_FOR_DISPATCH"] },
  { label: "All", status: [] },
];

/** The vendor's print queue: only orders assigned to them. */
export function VendorQueuePage() {
  const navigate = useNavigate();
  const [filter, setFilter] = useState(0);
  const [page, setPage] = useState(1);
  const status = FILTERS[filter]!.status;
  const orders = useQuery({
    queryKey: ["vendor", "orders", filter, page],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/vendor/orders", {
          params: { query: { status: status.length ? status : null, page, page_size: 25 } },
        }),
      ),
    refetchInterval: 60_000,
  });
  return (
    <div>
      <PageHeader title="Print queue" />
      <div className="mb-4 max-w-xs">
        <Select
          label="Show"
          value={filter}
          onChange={(e) => {
            setFilter(Number(e.target.value));
            setPage(1);
          }}
        >
          {FILTERS.map((f, i) => (
            <option key={f.label} value={i}>
              {f.label}
            </option>
          ))}
        </Select>
      </div>
      {orders.isPending && <Spinner />}
      {orders.isError && (
        <ErrorBox message={errorMessage(orders.error)} onRetry={() => void orders.refetch()} />
      )}
      {orders.data && (
        <>
          <Table
            columns={[
              {
                header: "Order",
                cell: (o) => <span className="font-mono font-medium">{o.code}</span>,
              },
              { header: "Status", cell: (o) => <StatusBadge status={o.status} /> },
              { header: "Item", cell: (o) => o.title },
              {
                header: "Spec",
                cell: (o) =>
                  [
                    o.pages && `${o.pages} pages`,
                    o.paper && humanize(o.paper),
                    o.binding && humanize(o.binding),
                  ]
                    .filter(Boolean)
                    .join(" · ") || "—",
              },
              { header: "Copies", cell: (o) => o.copies, className: "text-right" },
              { header: "City", cell: (o) => o.city_name },
              {
                header: "COD to collect",
                cell: (o) => (o.cod_amount_paisa ? formatPkr(o.cod_amount_paisa) : "Paid"),
                className: "text-right",
              },
              { header: "Assigned", cell: (o) => formatDateTime(o.assigned_at) },
            ]}
            rows={orders.data.items}
            rowKey={(o) => o.id}
            onRowClick={(o) => navigate(`/vendor/orders/${o.id}`)}
            empty="No orders assigned to you"
          />
          <Pagination
            page={page}
            pageSize={orders.data.page_size}
            total={orders.data.total}
            onPage={setPage}
          />
        </>
      )}
    </div>
  );
}
