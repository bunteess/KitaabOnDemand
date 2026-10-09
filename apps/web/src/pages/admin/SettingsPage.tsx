import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, errorMessage, unwrap, type Schemas } from "../../api/client";
import { Button, Card, ErrorBox, PageHeader, Spinner, TextInput } from "../../components/ui";
import { paisaToRupeesText, parseRupees } from "../../lib/format";

export function SettingsPage() {
  const settings = useQuery({
    queryKey: ["admin", "settings"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/settings", {})),
  });
  return (
    <div className="max-w-xl space-y-4">
      <PageHeader title="Settings" />
      {settings.isPending && <Spinner />}
      {settings.isError && (
        <ErrorBox message={errorMessage(settings.error)} onRetry={() => void settings.refetch()} />
      )}
      {settings.data && <SettingsForm initial={settings.data} />}
    </div>
  );
}

function SettingsForm({ initial }: { initial: Schemas["AppSettings"] }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(initial);
  const [codLimit, setCodLimit] = useState(
    initial.cod_max_order_value_paisa == null
      ? ""
      : paisaToRupeesText(initial.cod_max_order_value_paisa),
  );
  const [saved, setSaved] = useState(false);
  const save = useMutation({
    mutationFn: (body: Schemas["AppSettings"]) =>
      unwrap(api.PUT("/api/v1/admin/settings", { body })),
    onSuccess: (data) => {
      queryClient.setQueryData(["admin", "settings"], data);
      setSaved(true);
    },
  });
  const codInvalid = codLimit !== "" && parseRupees(codLimit) === null;
  return (
    <Card>
      <form
        className="space-y-3"
        onSubmit={(e) => {
          e.preventDefault();
          setSaved(false);
          save.mutate({
            ...form,
            cod_max_order_value_paisa: codLimit === "" ? null : parseRupees(codLimit),
          });
        }}
      >
        {save.isError && <ErrorBox message={errorMessage(save.error)} />}
        {saved && <p className="rounded bg-green-50 p-2 text-sm text-green-800">Saved.</p>}
        <TextInput
          label="Cash on delivery limit (Rs.)"
          hint="Orders above this total must be paid online. Leave blank for no limit."
          value={codLimit}
          onChange={(e) => setCodLimit(e.target.value)}
          error={codInvalid ? "Enter an amount or leave blank" : undefined}
        />
        <TextInput
          label="Default quote validity (hours)"
          inputMode="numeric"
          value={String(form.quote_validity_hours)}
          onChange={(e) => setForm({ ...form, quote_validity_hours: Number(e.target.value) || 48 })}
        />
        <TextInput
          label="Support phone"
          value={form.support_phone ?? ""}
          onChange={(e) => setForm({ ...form, support_phone: e.target.value })}
        />
        <TextInput
          label="Support WhatsApp"
          value={form.support_whatsapp ?? ""}
          onChange={(e) => setForm({ ...form, support_whatsapp: e.target.value })}
        />
        <TextInput
          label="Support email"
          type="email"
          value={form.support_email ?? ""}
          onChange={(e) => setForm({ ...form, support_email: e.target.value })}
        />
        <TextInput
          label="Support hours"
          value={form.support_hours ?? ""}
          onChange={(e) => setForm({ ...form, support_hours: e.target.value })}
        />
        <Button type="submit" busy={save.isPending} disabled={codInvalid}>
          Save settings
        </Button>
      </form>
    </Card>
  );
}
