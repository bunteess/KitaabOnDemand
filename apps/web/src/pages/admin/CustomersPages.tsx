import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api, errorMessage, unwrap, type Schemas } from "../../api/client";
import { StatusBadge } from "../../components/domain";
import { Pagination, Table, type Column } from "../../components/Table";
import {
  Button,
  Card,
  ErrorBox,
  KeyValue,
  PageHeader,
  Spinner,
  TextInput,
} from "../../components/ui";
import { formatDate, formatPkr } from "../../lib/format";

/** Read-only support view of customers. */
export function CustomersPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const customers = useQuery({
    queryKey: ["admin", "customers", q, page],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/customers", {
          params: { query: { q: q || null, page, page_size: 25 } },
        }),
      ),
  });
  const columns: Column<Schemas["CustomerSummary"]>[] = [
    { header: "Name", cell: (c) => c.full_name ?? "—" },
    { header: "Phone", cell: (c) => c.phone_masked },
    { header: "Orders", cell: (c) => c.order_count, className: "text-right" },
    { header: "Joined", cell: (c) => formatDate(c.created_at) },
    {
      header: "Notes",
      cell: (c) =>
        [c.deleted && "Deleted", c.is_review_account && "Store review account"]
          .filter(Boolean)
          .join(", ") || "—",
    },
  ];
  return (
    <div>
      <PageHeader title="Customers" />
      <form
        className="mb-4 flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setQ(search);
          setPage(1);
        }}
      >
        <div className="flex-1">
          <TextInput
            label="Search"
            placeholder="Phone or name"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>
      {customers.isPending && <Spinner />}
      {customers.isError && <ErrorBox message={errorMessage(customers.error)} />}
      {customers.data && (
        <>
          <Table
            columns={columns}
            rows={customers.data.items}
            rowKey={(c) => c.id}
            onRowClick={(c) => navigate(`/admin/customers/${c.id}`)}
          />
          <Pagination
            page={page}
            pageSize={customers.data.page_size}
            total={customers.data.total}
            onPage={setPage}
          />
        </>
      )}
    </div>
  );
}

export function CustomerDetailPage() {
  const { userId = "" } = useParams();
  const navigate = useNavigate();
  const customer = useQuery({
    queryKey: ["admin", "customer", userId],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/customers/{user_id}", { params: { path: { user_id: userId } } }),
      ),
  });
  if (customer.isPending) return <Spinner />;
  if (customer.isError) return <ErrorBox message={errorMessage(customer.error)} />;
  const c = customer.data;
  return (
    <div className="space-y-4">
      <Link to="/admin/customers" className="text-sm text-brand-800 hover:underline">
        ← Customers
      </Link>
      <Card title={c.full_name ?? "Customer"}>
        <KeyValue
          items={[
            ["Phone", c.phone_e164],
            ["Email", c.email],
            ["Google linked", c.google_linked ? "Yes" : "No"],
            ["Joined", formatDate(c.created_at)],
            ["Deleted", c.deleted_at ? formatDate(c.deleted_at) : "No"],
          ]}
        />
      </Card>
      <Card title="Orders">
        <Table
          columns={[
            { header: "Order", cell: (o) => <span className="font-mono">{o.code}</span> },
            { header: "Status", cell: (o) => <StatusBadge status={o.status} /> },
            { header: "Item", cell: (o) => o.title },
            {
              header: "Total",
              cell: (o) => (o.total_paisa == null ? "—" : formatPkr(o.total_paisa)),
            },
            { header: "Created", cell: (o) => formatDate(o.created_at) },
          ]}
          rows={c.orders}
          rowKey={(o) => o.id}
          onRowClick={(o) => navigate(`/admin/orders/${o.id}`)}
        />
      </Card>
    </div>
  );
}
