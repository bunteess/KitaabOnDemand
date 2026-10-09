import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, download, errorMessage, unwrap, type Schemas } from "../../api/client";
import { Pagination, Table } from "../../components/Table";
import {
  Button,
  Card,
  Checkbox,
  ErrorBox,
  PageHeader,
  Select,
  Spinner,
  TextInput,
} from "../../components/ui";
import { formatDate, formatDateTime, formatPkr, todayInPakistan } from "../../lib/format";

function daysBefore(iso: string, days: number) {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - days);
  return d.toISOString().slice(0, 10);
}

function CsvButton({ path, filename }: { path: string; filename: string }) {
  const [error, setError] = useState<string | null>(null);
  return (
    <>
      <Button
        variant="secondary"
        onClick={() => download(path, filename).catch((e) => setError(errorMessage(e)))}
      >
        Export CSV
      </Button>
      {error && <ErrorBox message={error} />}
    </>
  );
}

export function RevenuePage() {
  const today = todayInPakistan();
  const [from, setFrom] = useState(daysBefore(today, 30));
  const [to, setTo] = useState(today);
  const report = useQuery({
    queryKey: ["admin", "revenue", from, to],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/finance/daily-revenue", {
          params: { query: { from_date: from, to_date: to } },
        }),
      ),
  });
  return (
    <div className="space-y-4">
      <PageHeader
        title="Daily revenue"
        actions={
          <CsvButton
            path={`/api/v1/admin/finance/daily-revenue.csv?from_date=${from}&to_date=${to}`}
            filename={`revenue-${from}-${to}.csv`}
          />
        }
      >
        <p className="text-sm text-slate-600">
          By Pakistan calendar day and payment method. COD counts when the courier collects the
          cash.
        </p>
      </PageHeader>
      <div className="flex flex-wrap gap-3">
        <TextInput
          label="From"
          type="date"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
        />
        <TextInput label="To" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
      </div>
      {report.isPending && <Spinner />}
      {report.isError && <ErrorBox message={errorMessage(report.error)} />}
      {report.data && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Card title="Gross">{formatPkr(report.data.total_gross_paisa)}</Card>
            <Card title="Refunds">{formatPkr(report.data.total_refunds_paisa)}</Card>
            <Card title="Net">{formatPkr(report.data.total_net_paisa)}</Card>
          </div>
          <Table
            columns={[
              { header: "Date", cell: (r) => formatDate(`${r.date}T12:00:00Z`) },
              { header: "Method", cell: (r) => r.payment_method },
              { header: "Orders", cell: (r) => r.orders, className: "text-right" },
              { header: "Gross", cell: (r) => formatPkr(r.gross_paisa), className: "text-right" },
              {
                header: "Refunds",
                cell: (r) => formatPkr(r.refunds_paisa),
                className: "text-right",
              },
              { header: "Net", cell: (r) => formatPkr(r.net_paisa), className: "text-right" },
            ]}
            rows={report.data.rows}
            rowKey={(r) => `${r.date}-${r.payment_method}`}
            empty="No revenue in this period"
          />
        </>
      )}
    </div>
  );
}

export function CodPage() {
  const queryClient = useQueryClient();
  const pending = useQuery({
    queryKey: ["admin", "cod"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/finance/cod-pending", {})),
  });
  return (
    <div className="space-y-4">
      <PageHeader
        title="COD pending"
        actions={
          <CsvButton path="/api/v1/admin/finance/cod-pending.csv" filename="cod-pending.csv" />
        }
      >
        <p className="text-sm text-slate-600">
          Cash couriers have collected and not yet sent to us. Marking it remitted completes the
          orders.
        </p>
      </PageHeader>
      {pending.isPending && <Spinner />}
      {pending.isError && <ErrorBox message={errorMessage(pending.error)} />}
      {pending.data?.length === 0 && <Card>No cash pending.</Card>}
      {pending.data?.map((group) => (
        <CodGroup
          key={group.courier_code}
          group={group}
          onDone={() => void queryClient.invalidateQueries({ queryKey: ["admin", "cod"] })}
        />
      ))}
    </div>
  );
}

function CodGroup({ group, onDone }: { group: Schemas["CodPendingGroup"]; onDone: () => void }) {
  const [selected, setSelected] = useState<string[]>([]);
  const [reference, setReference] = useState("");
  const remit = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/admin/finance/cod-remittances", {
          body: { courier_code: group.courier_code, order_ids: selected, reference },
        }),
      ),
    onSuccess: () => {
      setSelected([]);
      setReference("");
      onDone();
    },
  });
  const selectedTotal = group.orders
    .filter((o) => selected.includes(o.order_id))
    .reduce((a, o) => a + o.amount_paisa, 0);
  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]));
  return (
    <Card title={`${group.courier_name}: ${formatPkr(group.total_paisa)}`}>
      {remit.isError && <ErrorBox message={errorMessage(remit.error)} />}
      <Table
        columns={[
          {
            header: "",
            cell: (o) => (
              <Checkbox
                label=""
                aria-label={`Select ${o.order_code}`}
                checked={selected.includes(o.order_id)}
                onChange={() => toggle(o.order_id)}
              />
            ),
          },
          { header: "Order", cell: (o) => <span className="font-mono">{o.order_code}</span> },
          { header: "CN", cell: (o) => o.cn_number ?? "—" },
          { header: "Amount", cell: (o) => formatPkr(o.amount_paisa), className: "text-right" },
          { header: "Delivered", cell: (o) => formatDateTime(o.delivered_at) },
        ]}
        rows={group.orders}
        rowKey={(o) => o.order_id}
      />
      <form
        className="mt-3 flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          remit.mutate();
        }}
      >
        <Button variant="ghost" onClick={() => setSelected(group.orders.map((o) => o.order_id))}>
          Select all
        </Button>
        <div className="flex-1">
          <TextInput
            label="Remittance reference"
            required
            value={reference}
            onChange={(e) => setReference(e.target.value)}
          />
        </div>
        <Button
          type="submit"
          busy={remit.isPending}
          disabled={selected.length === 0 || !reference.trim()}
        >
          Mark {formatPkr(selectedTotal)} remitted
        </Button>
      </form>
    </Card>
  );
}

export function PayoutsPage() {
  const queryClient = useQueryClient();
  const payouts = useQuery({
    queryKey: ["admin", "payouts"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/finance/vendor-payouts", {})),
  });
  const batches = useQuery({
    queryKey: ["admin", "batches"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/finance/payout-batches", {})),
  });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin", "payouts"] });
    void queryClient.invalidateQueries({ queryKey: ["admin", "batches"] });
  };
  const create = useMutation({
    mutationFn: (vendorId: string) =>
      unwrap(api.POST("/api/v1/admin/finance/payout-batches", { body: { vendor_id: vendorId } })),
    onSuccess: refresh,
  });
  return (
    <div className="space-y-4">
      <PageHeader
        title="Vendor payouts"
        actions={
          <CsvButton
            path="/api/v1/admin/finance/vendor-payouts.csv"
            filename="vendor-payouts.csv"
          />
        }
      />
      {create.isError && <ErrorBox message={errorMessage(create.error)} />}
      {payouts.isPending && <Spinner />}
      {payouts.data && (
        <Table
          columns={[
            { header: "Vendor", cell: (v) => v.vendor_name },
            { header: "Accrued", cell: (v) => formatPkr(v.accrued_paisa), className: "text-right" },
            { header: "Paid", cell: (v) => formatPkr(v.paid_paisa), className: "text-right" },
            {
              header: "In open batches",
              cell: (v) => formatPkr(v.in_open_batches_paisa),
              className: "text-right",
            },
            {
              header: "Owed",
              cell: (v) => <strong>{formatPkr(v.owed_paisa)}</strong>,
              className: "text-right",
            },
            {
              header: "",
              cell: (v) => (
                <Button
                  variant="secondary"
                  busy={create.isPending && create.variables === v.vendor_id}
                  disabled={v.owed_paisa - v.in_open_batches_paisa <= 0}
                  onClick={() => create.mutate(v.vendor_id)}
                >
                  Create batch
                </Button>
              ),
            },
          ]}
          rows={payouts.data}
          rowKey={(v) => v.vendor_id}
        />
      )}
      <h2 className="text-lg font-semibold">Payout batches</h2>
      {batches.data?.length === 0 && <Card>No batches yet.</Card>}
      {batches.data?.map((b) => (
        <BatchCard key={b.id} batch={b} onDone={refresh} />
      ))}
    </div>
  );
}

function BatchCard({ batch, onDone }: { batch: Schemas["PayoutBatchOut"]; onDone: () => void }) {
  const [reference, setReference] = useState("");
  const pay = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/admin/finance/payout-batches/{batch_id}/mark-paid", {
          params: { path: { batch_id: batch.id } },
          body: { reference },
        }),
      ),
    onSuccess: onDone,
  });
  return (
    <Card
      title={`${batch.vendor_name}: ${formatPkr(batch.total_paisa)} · ${batch.status}`}
      actions={
        <CsvButton
          path={`/api/v1/admin/finance/payout-batches/${batch.id}.csv`}
          filename={`payout-${batch.id}.csv`}
        />
      }
    >
      <ul className="mb-3 text-sm">
        {batch.items.map((i) => (
          <li key={i.order_id}>
            <span className="font-mono">{i.order_code}</span> · {formatPkr(i.amount_paisa)}
          </li>
        ))}
      </ul>
      {batch.status === "PAID" ? (
        <p className="text-sm text-slate-600">
          Paid {formatDateTime(batch.paid_at)} · reference {batch.reference}
        </p>
      ) : (
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            pay.mutate();
          }}
        >
          {pay.isError && <ErrorBox message={errorMessage(pay.error)} />}
          <div className="flex-1">
            <TextInput
              label="Payment reference"
              required
              value={reference}
              onChange={(e) => setReference(e.target.value)}
            />
          </div>
          <Button type="submit" busy={pay.isPending} disabled={!reference.trim()}>
            Mark paid
          </Button>
        </form>
      )}
    </Card>
  );
}

export function RefundsPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<"" | Schemas["RefundStatus"]>("PENDING");
  const [page, setPage] = useState(1);
  const refunds = useQuery({
    queryKey: ["admin", "refunds", status, page],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/refunds", {
          params: { query: { status: status || null, page, page_size: 25 } },
        }),
      ),
  });
  const [references, setReferences] = useState<Record<string, string>>({});
  const process = useMutation({
    mutationFn: ({ id, reference }: { id: string; reference: string }) =>
      unwrap(
        api.POST("/api/v1/admin/refunds/{refund_id}/mark-processed", {
          params: { path: { refund_id: id } },
          body: { reference },
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["admin", "refunds"] }),
  });
  return (
    <div className="space-y-4">
      <PageHeader title="Refunds">
        <p className="text-sm text-slate-600">
          Refund through the gateway, then record the reference here.
        </p>
      </PageHeader>
      <div className="max-w-xs">
        <Select
          label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value as typeof status)}
        >
          <option value="PENDING">Pending</option>
          <option value="PROCESSED">Processed</option>
          <option value="">All</option>
        </Select>
      </div>
      {process.isError && <ErrorBox message={errorMessage(process.error)} />}
      {refunds.isPending && <Spinner />}
      {refunds.data && (
        <>
          <Table
            columns={[
              { header: "Order", cell: (r) => <span className="font-mono">{r.order_code}</span> },
              { header: "Amount", cell: (r) => formatPkr(r.amount_paisa), className: "text-right" },
              { header: "Reason", cell: (r) => r.reason },
              { header: "Created", cell: (r) => formatDateTime(r.created_at) },
              {
                header: "Reference",
                cell: (r) =>
                  r.status === "PROCESSED" ? (
                    r.reference
                  ) : (
                    <div className="flex items-end gap-2">
                      <TextInput
                        label="Reference"
                        value={references[r.id] ?? ""}
                        onChange={(e) => setReferences({ ...references, [r.id]: e.target.value })}
                      />
                      <Button
                        disabled={!references[r.id]?.trim()}
                        onClick={() => process.mutate({ id: r.id, reference: references[r.id]! })}
                      >
                        Mark done
                      </Button>
                    </div>
                  ),
              },
            ]}
            rows={refunds.data.items}
            rowKey={(r) => r.id}
            empty="No refunds"
          />
          <Pagination
            page={page}
            pageSize={refunds.data.page_size}
            total={refunds.data.total}
            onPage={setPage}
          />
        </>
      )}
    </div>
  );
}
