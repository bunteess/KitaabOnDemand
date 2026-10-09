import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorMessage, unwrap, type Schemas } from "../../api/client";
import { Table, type Column } from "../../components/Table";
import { Button, Card, ErrorBox, PageHeader, Spinner, TextInput } from "../../components/ui";
import { formatDateTime } from "../../lib/format";
import { StaffCreatedDialog } from "./StaffCreated";

export function StaffPage() {
  const queryClient = useQueryClient();
  const admins = useQuery({
    queryKey: ["admin", "staff"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/staff", {})),
  });
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [created, setCreated] = useState<Schemas["StaffUserCreated"] | null>(null);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["admin", "staff"] });
  const create = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/admin/staff", { body: { email, full_name: name } })),
    onSuccess: (result) => {
      setCreated(result);
      setEmail("");
      setName("");
      refresh();
    },
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas["StaffUserUpdate"] }) =>
      unwrap(
        api.PATCH("/api/v1/admin/staff/{user_id}", { params: { path: { user_id: id } }, body }),
      ),
    onSuccess: refresh,
  });

  const columns: Column<Schemas["StaffUserOut"]>[] = [
    { header: "Email", cell: (u) => u.email },
    { header: "Name", cell: (u) => u.full_name ?? "—" },
    { header: "Status", cell: (u) => (u.locked ? "Locked" : u.is_active ? "Active" : "Inactive") },
    { header: "Last sign-in", cell: (u) => formatDateTime(u.last_login_at) },
    {
      header: "",
      cell: (u) => (
        <div className="flex gap-2">
          {u.locked && (
            <Button
              variant="secondary"
              onClick={() => update.mutate({ id: u.id, body: { unlock: true } })}
            >
              Unlock
            </Button>
          )}
          <Button
            variant="secondary"
            onClick={() =>
              update.mutate({ id: u.id, body: { is_active: !u.is_active, unlock: false } })
            }
          >
            {u.is_active ? "Deactivate" : "Reactivate"}
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title="Admins" />
      {update.isError && <ErrorBox message={errorMessage(update.error)} />}
      {admins.isPending && <Spinner />}
      {admins.data && <Table columns={columns} rows={admins.data} rowKey={(u) => u.id} />}
      <Card title="Add an admin">
        <form
          className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate();
          }}
        >
          <TextInput
            label="Email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <TextInput
            label="Full name"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Button type="submit" busy={create.isPending}>
            Create admin
          </Button>
        </form>
        {create.isError && (
          <div className="mt-2">
            <ErrorBox message={errorMessage(create.error)} />
          </div>
        )}
        <p className="mt-2 text-xs text-slate-500">
          Admins must set up an authenticator app (TOTP) with the link shown after creation.
        </p>
      </Card>
      <StaffCreatedDialog created={created} onClose={() => setCreated(null)} />
    </div>
  );
}
