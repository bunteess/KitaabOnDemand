import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError, errorMessage, unwrap, type Schemas } from "../../api/client";
import { Table, type Column } from "../../components/Table";
import {
  Button,
  Card,
  Checkbox,
  Dialog,
  ErrorBox,
  PageHeader,
  Select,
  Spinner,
  TextArea,
  TextInput,
} from "../../components/ui";
import { formatDateTime } from "../../lib/format";
import { StaffCreatedDialog } from "./StaffCreated";

type Vendor = Schemas["VendorOut"];

export function VendorsPage() {
  const vendors = useQuery({
    queryKey: ["admin", "vendors"],
    queryFn: () =>
      unwrap(api.GET("/api/v1/admin/vendors", { params: { query: { include_inactive: true } } })),
  });
  const [editing, setEditing] = useState<Vendor | "new" | null>(null);
  const [usersOf, setUsersOf] = useState<Vendor | null>(null);

  const columns: Column<Vendor>[] = [
    { header: "Name", cell: (v) => <span className="font-medium">{v.name}</span> },
    { header: "Contact", cell: (v) => `${v.contact_name}, ${v.contact_phone_e164}` },
    { header: "Email", cell: (v) => v.email ?? "—" },
    { header: "Status", cell: (v) => (v.is_active ? "Active" : "Inactive") },
    {
      header: "",
      cell: (v) => (
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setEditing(v)}>
            Edit
          </Button>
          <Button variant="secondary" onClick={() => setUsersOf(v)}>
            Logins
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Vendors"
        actions={<Button onClick={() => setEditing("new")}>Add vendor</Button>}
      />
      {vendors.isPending && <Spinner />}
      {vendors.isError && (
        <ErrorBox message={errorMessage(vendors.error)} onRetry={() => void vendors.refetch()} />
      )}
      {vendors.data && (
        <Table columns={columns} rows={vendors.data} rowKey={(v) => v.id} empty="No vendors yet" />
      )}
      {editing && (
        <VendorForm vendor={editing === "new" ? null : editing} onClose={() => setEditing(null)} />
      )}
      {usersOf && <VendorUsers vendor={usersOf} onClose={() => setUsersOf(null)} />}
    </div>
  );
}

function VendorForm({ vendor, onClose }: { vendor: Vendor | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const cities = useQuery({
    queryKey: ["admin", "cities"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/cities", {})),
  });
  const [form, setForm] = useState<Schemas["VendorIn"]>({
    name: vendor?.name ?? "",
    contact_name: vendor?.contact_name ?? "",
    contact_phone: vendor?.contact_phone_e164 ?? "",
    email: vendor?.email ?? null,
    city_id: vendor?.city_id ?? null,
    address: vendor?.address ?? null,
    is_active: vendor?.is_active ?? true,
  });
  const save = useMutation({
    mutationFn: () =>
      vendor
        ? unwrap(
            api.PUT("/api/v1/admin/vendors/{vendor_id}", {
              params: { path: { vendor_id: vendor.id } },
              body: form,
            }),
          )
        : unwrap(api.POST("/api/v1/admin/vendors", { body: form })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "vendors"] });
      onClose();
    },
  });
  const fieldErrors = save.error instanceof ApiError ? save.error.fieldErrors() : {};
  const set = <K extends keyof Schemas["VendorIn"]>(key: K, value: Schemas["VendorIn"][K]) =>
    setForm((f) => ({ ...f, [key]: value }));
  return (
    <Dialog title={vendor ? "Edit vendor" : "Add vendor"} open onClose={onClose}>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        {save.isError && <ErrorBox message={errorMessage(save.error)} />}
        <TextInput
          label="Name"
          required
          value={form.name}
          onChange={(e) => set("name", e.target.value)}
          error={fieldErrors.name}
        />
        <TextInput
          label="Contact name"
          required
          value={form.contact_name}
          onChange={(e) => set("contact_name", e.target.value)}
          error={fieldErrors.contact_name}
        />
        <TextInput
          label="Contact phone"
          required
          value={form.contact_phone}
          onChange={(e) => set("contact_phone", e.target.value)}
          error={fieldErrors.contact_phone}
        />
        <TextInput
          label="Email"
          type="email"
          value={form.email ?? ""}
          onChange={(e) => set("email", e.target.value || null)}
          error={fieldErrors.email}
        />
        <Select
          label="City"
          value={form.city_id ?? ""}
          onChange={(e) => set("city_id", e.target.value || null)}
        >
          <option value="">—</option>
          {cities.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </Select>
        <TextArea
          label="Address"
          value={form.address ?? ""}
          onChange={(e) => set("address", e.target.value || null)}
        />
        <Checkbox
          label="Active"
          checked={form.is_active}
          onChange={(e) => set("is_active", e.target.checked)}
        />
        <Button type="submit" busy={save.isPending}>
          Save
        </Button>
      </form>
    </Dialog>
  );
}

function VendorUsers({ vendor, onClose }: { vendor: Vendor; onClose: () => void }) {
  const queryClient = useQueryClient();
  const key = ["admin", "vendor-users", vendor.id];
  const users = useQuery({
    queryKey: key,
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/admin/vendors/{vendor_id}/users", {
          params: { path: { vendor_id: vendor.id } },
        }),
      ),
  });
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [created, setCreated] = useState<Schemas["StaffUserCreated"] | null>(null);
  // Deactivating a login signs that person out everywhere (docs/RUNBOOK.md).
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Schemas["StaffUserUpdate"] }) =>
      unwrap(
        api.PATCH("/api/v1/admin/staff/{user_id}", { params: { path: { user_id: id } }, body }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: key }),
  });
  const create = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/admin/vendors/{vendor_id}/users", {
          params: { path: { vendor_id: vendor.id } },
          body: { email, full_name: name },
        }),
      ),
    onSuccess: (result) => {
      setCreated(result);
      setEmail("");
      setName("");
      void queryClient.invalidateQueries({ queryKey: key });
    },
  });
  return (
    <Dialog title={`${vendor.name}: logins`} open onClose={onClose}>
      <div className="space-y-4">
        {update.isError && <ErrorBox message={errorMessage(update.error)} />}
        {users.data && (
          <ul className="space-y-2 text-sm">
            {users.data.length === 0 && <li className="text-slate-500">No logins yet.</li>}
            {users.data.map((u) => (
              <li key={u.id} className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  {u.email} · {u.full_name} ·{" "}
                  {u.locked ? "locked" : u.is_active ? "active" : "inactive"} · last sign-in{" "}
                  {formatDateTime(u.last_login_at)}
                </span>
                <span className="flex gap-2">
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
                    aria-label={`${u.is_active ? "Deactivate" : "Reactivate"} ${u.email}`}
                    onClick={() =>
                      update.mutate({ id: u.id, body: { is_active: !u.is_active, unlock: false } })
                    }
                  >
                    {u.is_active ? "Deactivate" : "Reactivate"}
                  </Button>
                </span>
              </li>
            ))}
          </ul>
        )}
        <Card title="Add a login">
          <form
            className="space-y-2"
            onSubmit={(e) => {
              e.preventDefault();
              create.mutate();
            }}
          >
            {create.isError && <ErrorBox message={errorMessage(create.error)} />}
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
              Create login
            </Button>
          </form>
        </Card>
      </div>
      <StaffCreatedDialog created={created} onClose={() => setCreated(null)} />
    </Dialog>
  );
}
