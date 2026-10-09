import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorMessage, unwrap, type Schemas } from "../../api/client";
import { Table } from "../../components/Table";
import {
  Button,
  Checkbox,
  Dialog,
  ErrorBox,
  PageHeader,
  Spinner,
  TextInput,
} from "../../components/ui";

type City = Schemas["CityAdminOut"];

export function CitiesPage() {
  const cities = useQuery({
    queryKey: ["admin", "cities"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/cities", {})),
  });
  const pricing = useQuery({
    queryKey: ["admin", "pricing"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/pricing-configs", {})),
  });
  const [editing, setEditing] = useState<City | "new" | null>(null);
  const zones = new Set(
    Object.keys(pricing.data?.find((v) => v.active)?.rules.delivery_fees_paisa ?? {}),
  );
  return (
    <div>
      <PageHeader
        title="Cities and zones"
        actions={<Button onClick={() => setEditing("new")}>Add city</Button>}
      />
      {cities.isPending && <Spinner />}
      {cities.isError && <ErrorBox message={errorMessage(cities.error)} />}
      {cities.data && (
        <Table
          columns={[
            { header: "City", cell: (c) => c.name },
            { header: "Province", cell: (c) => c.province },
            {
              header: "Zone",
              cell: (c) => (
                <span>
                  {c.zone_code}
                  {pricing.data && !zones.has(c.zone_code) && (
                    <span className="ml-2 text-xs text-red-700">no delivery fee for this zone</span>
                  )}
                </span>
              ),
            },
            { header: "Active", cell: (c) => (c.is_active ? "Yes" : "No") },
            { header: "Order", cell: (c) => c.sort_order },
            {
              header: "",
              cell: (c) => (
                <Button variant="secondary" onClick={() => setEditing(c)}>
                  Edit
                </Button>
              ),
            },
          ]}
          rows={cities.data}
          rowKey={(c) => c.id}
        />
      )}
      {editing && (
        <CityForm city={editing === "new" ? null : editing} onClose={() => setEditing(null)} />
      )}
    </div>
  );
}

function CityForm({ city, onClose }: { city: City | null; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<Schemas["CityIn"]>({
    name: city?.name ?? "",
    province: city?.province ?? "",
    zone_code: city?.zone_code ?? "",
    is_active: city?.is_active ?? true,
    sort_order: city?.sort_order ?? 0,
  });
  const save = useMutation({
    mutationFn: () =>
      city
        ? unwrap(
            api.PUT("/api/v1/admin/cities/{city_id}", {
              params: { path: { city_id: city.id } },
              body: form,
            }),
          )
        : unwrap(api.POST("/api/v1/admin/cities", { body: form })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "cities"] });
      onClose();
    },
  });
  return (
    <Dialog title={city ? "Edit city" : "Add city"} open onClose={onClose}>
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
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <TextInput
          label="Province"
          required
          value={form.province}
          onChange={(e) => setForm({ ...form, province: e.target.value })}
        />
        <TextInput
          label="Courier zone code"
          required
          value={form.zone_code}
          onChange={(e) => setForm({ ...form, zone_code: e.target.value })}
        />
        <TextInput
          label="Sort order"
          inputMode="numeric"
          value={String(form.sort_order ?? 0)}
          onChange={(e) => setForm({ ...form, sort_order: Number(e.target.value) || 0 })}
        />
        <Checkbox
          label="Active"
          checked={form.is_active ?? true}
          onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
        />
        <Button type="submit" busy={save.isPending}>
          Save
        </Button>
      </form>
    </Dialog>
  );
}
