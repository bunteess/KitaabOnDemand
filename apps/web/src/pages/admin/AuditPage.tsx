import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorMessage, unwrap } from "../../api/client";
import { Pagination, Table } from "../../components/Table";
import { Button, ErrorBox, PageHeader, Spinner, TextInput } from "../../components/ui";
import { formatDateTime } from "../../lib/format";

export function AuditPage() {
  const [action, setAction] = useState("");
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const logs = useQuery({
    queryKey: ["admin", "audit", filter, page],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/audit-logs", {
          params: { query: { action: filter || null, page, page_size: 50 } },
        }),
      ),
  });
  return (
    <div>
      <PageHeader title="Audit log" />
      <form
        className="mb-4 flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setFilter(action);
          setPage(1);
        }}
      >
        <div className="flex-1">
          <TextInput
            label="Action"
            placeholder="e.g. file.download, order.reject, purge.run"
            value={action}
            onChange={(e) => setAction(e.target.value)}
          />
        </div>
        <Button type="submit" variant="secondary">
          Filter
        </Button>
      </form>
      {logs.isPending && <Spinner />}
      {logs.isError && <ErrorBox message={errorMessage(logs.error)} />}
      {logs.data && (
        <>
          <Table
            columns={[
              {
                header: "Time",
                cell: (l) => (
                  <span className="whitespace-nowrap">{formatDateTime(l.created_at)}</span>
                ),
              },
              {
                header: "Actor",
                cell: (l) =>
                  `${l.actor_name ?? "System"}${l.actor_role ? ` (${l.actor_role})` : ""}`,
              },
              { header: "Action", cell: (l) => <code>{l.action}</code> },
              {
                header: "Entity",
                cell: (l) => `${l.entity_type}${l.entity_id ? ` ${l.entity_id.slice(0, 8)}` : ""}`,
              },
              {
                header: "Details",
                cell: (l) => <code className="text-xs break-all">{JSON.stringify(l.details)}</code>,
              },
            ]}
            rows={logs.data.items}
            rowKey={(l) => l.id}
          />
          <Pagination
            page={page}
            pageSize={logs.data.page_size}
            total={logs.data.total}
            onPage={setPage}
          />
        </>
      )}
    </div>
  );
}
