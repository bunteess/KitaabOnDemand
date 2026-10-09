import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, ApiError, errorMessage, unwrap, type Schemas } from "../../api/client";
import { BINDINGS, PAPERS } from "../../components/domain";
import { Table } from "../../components/Table";
import {
  Button,
  Card,
  ErrorBox,
  PageHeader,
  Spinner,
  TextArea,
  TextInput,
} from "../../components/ui";
import {
  formatDateTime,
  formatPkr,
  humanize,
  paisaToRupeesText,
  parseRupees,
} from "../../lib/format";

type Rules = Schemas["PricingRules"];

const paperOf = (rules: Rules, paper: string) =>
  rules.papers[paper] ?? { rate_per_page_paisa: 0, brackets: [] };
const bindingOf = (rules: Rules, binding: string) =>
  rules.bindings[binding] ?? { fee_paisa: 0, max_pages: null };

/** Pricing versions. A new version takes effect from its date; old orders keep theirs. */
export function PricingPage() {
  const versions = useQuery({
    queryKey: ["admin", "pricing"],
    queryFn: () => unwrap(api.GET("/api/v1/admin/pricing-configs", {})),
  });
  const [editing, setEditing] = useState(false);
  if (versions.isPending) return <Spinner />;
  if (versions.isError)
    return (
      <ErrorBox message={errorMessage(versions.error)} onRetry={() => void versions.refetch()} />
    );
  const active = versions.data.find((v) => v.active) ?? versions.data[0];
  return (
    <div className="space-y-4">
      <PageHeader
        title="Pricing"
        actions={
          !editing && active && <Button onClick={() => setEditing(true)}>New version</Button>
        }
      >
        <p className="text-sm text-slate-600">
          All amounts are in rupees. Orders keep the version they were priced with.
        </p>
      </PageHeader>
      {editing && active && <PricingForm base={active.rules} onDone={() => setEditing(false)} />}
      {active && <RulesSummary rules={active.rules} />}
      <Card title="Version history">
        <Table
          columns={[
            { header: "Version", cell: (v) => `v${v.version}${v.active ? " (active)" : ""}` },
            { header: "Effective from", cell: (v) => formatDateTime(v.effective_from) },
            { header: "Notes", cell: (v) => v.notes ?? "—" },
            { header: "By", cell: (v) => v.created_by_name ?? "—" },
            { header: "Created", cell: (v) => formatDateTime(v.created_at) },
          ]}
          rows={versions.data}
          rowKey={(v) => String(v.version)}
        />
      </Card>
    </div>
  );
}

function RulesSummary({ rules }: { rules: Rules }) {
  return (
    <Card title="Current rates">
      <div className="grid gap-4 text-sm md:grid-cols-3">
        <div>
          <h3 className="font-medium">Paper (per page)</h3>
          {PAPERS.map((p) => (
            <p key={p}>
              {humanize(p)}: {formatPkr(paperOf(rules, p).rate_per_page_paisa)}
              {paperOf(rules, p).brackets?.map(
                (b) => ` · ${formatPkr(b.rate_per_page_paisa)} from ${b.min_printed_pages} pages`,
              )}
            </p>
          ))}
        </div>
        <div>
          <h3 className="font-medium">Binding (per copy)</h3>
          {BINDINGS.map((b) => (
            <p key={b}>
              {humanize(b)}: {formatPkr(bindingOf(rules, b).fee_paisa)}{" "}
              {bindingOf(rules, b).max_pages ? `· max ${bindingOf(rules, b).max_pages} pages` : ""}
            </p>
          ))}
        </div>
        <div>
          <h3 className="font-medium">Delivery and COD</h3>
          {Object.entries(rules.delivery_fees_paisa).map(([zone, fee]) => (
            <p key={zone}>
              Zone {zone}: {formatPkr(fee)}
            </p>
          ))}
          <p>COD fee: {formatPkr(rules.cod_fee_paisa)}</p>
          <p>Max copies: {rules.max_copies}</p>
        </div>
      </div>
    </Card>
  );
}

type Draft = {
  papers: Record<string, { rate: string; brackets: { min: string; rate: string }[] }>;
  bindings: Record<string, { fee: string; max: string }>;
  zones: { zone: string; fee: string }[];
  cod: string;
  maxCopies: string;
};

function toDraft(rules: Rules): Draft {
  return {
    papers: Object.fromEntries(
      PAPERS.map((p) => [
        p,
        {
          rate: paisaToRupeesText(paperOf(rules, p).rate_per_page_paisa),
          brackets: (paperOf(rules, p).brackets ?? []).map((b) => ({
            min: String(b.min_printed_pages),
            rate: paisaToRupeesText(b.rate_per_page_paisa),
          })),
        },
      ]),
    ),
    bindings: Object.fromEntries(
      BINDINGS.map((b) => [
        b,
        {
          fee: paisaToRupeesText(bindingOf(rules, b).fee_paisa),
          max: bindingOf(rules, b).max_pages ? String(bindingOf(rules, b).max_pages) : "",
        },
      ]),
    ),
    zones: Object.entries(rules.delivery_fees_paisa).map(([zone, fee]) => ({
      zone,
      fee: paisaToRupeesText(fee),
    })),
    cod: paisaToRupeesText(rules.cod_fee_paisa),
    maxCopies: String(rules.max_copies ?? 50),
  };
}

/** Converts the form back to paisa. Returns an error message for the first bad field. */
export function fromDraft(d: Draft): Rules | string {
  const money = (label: string, text: string) => {
    const v = parseRupees(text);
    if (v === null) throw new Error(`${label}: enter an amount like 2.50`);
    return v;
  };
  try {
    return {
      papers: Object.fromEntries(
        PAPERS.map((p) => [
          p,
          {
            rate_per_page_paisa: money(`${humanize(p)} rate`, d.papers[p]!.rate),
            brackets: d.papers[p]!.brackets.map((b) => ({
              min_printed_pages: Number(b.min),
              rate_per_page_paisa: money(`${humanize(p)} bracket`, b.rate),
            })),
          },
        ]),
      ) as Rules["papers"],
      bindings: Object.fromEntries(
        BINDINGS.map((b) => [
          b,
          {
            fee_paisa: money(`${humanize(b)} fee`, d.bindings[b]!.fee),
            max_pages: d.bindings[b]!.max ? Number(d.bindings[b]!.max) : null,
          },
        ]),
      ) as Rules["bindings"],
      delivery_fees_paisa: Object.fromEntries(
        d.zones
          .filter((z) => z.zone.trim())
          .map((z) => [z.zone.trim(), money(`Zone ${z.zone} fee`, z.fee)]),
      ),
      cod_fee_paisa: money("COD fee", d.cod),
      max_copies: Number(d.maxCopies) || 50,
    };
  } catch (error) {
    return (error as Error).message;
  }
}

function PricingForm({ base, onDone }: { base: Rules; onDone: () => void }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState(() => toDraft(base));
  const [effectiveFrom, setEffectiveFrom] = useState(() => new Date().toISOString().slice(0, 16));
  const [notes, setNotes] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const save = useMutation({
    mutationFn: (rules: Rules) =>
      unwrap(
        api.POST("/api/v1/admin/pricing-configs", {
          body: {
            effective_from: new Date(effectiveFrom).toISOString(),
            rules,
            notes: notes || null,
          },
        }),
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["admin", "pricing"] });
      onDone();
    },
  });
  const update = (fn: (d: Draft) => void) =>
    setDraft((d) => {
      const copy = structuredClone(d);
      fn(copy);
      return copy;
    });
  const serverErrors =
    save.error instanceof ApiError ? Object.entries(save.error.fieldErrors()) : [];

  return (
    <Card title="New pricing version">
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          const rules = fromDraft(draft);
          if (typeof rules === "string") {
            setLocalError(rules);
            return;
          }
          setLocalError(null);
          save.mutate(rules);
        }}
      >
        {localError && <ErrorBox message={localError} />}
        {save.isError && <ErrorBox message={errorMessage(save.error)} />}
        {serverErrors.map(([field, message]) => (
          <p key={field} className="text-sm text-red-700">
            {field}: {message}
          </p>
        ))}
        <div className="grid gap-4 md:grid-cols-2">
          {PAPERS.map((p) => (
            <fieldset key={p} className="space-y-2 rounded border border-slate-200 p-3">
              <legend className="px-1 text-sm font-medium">{humanize(p)}</legend>
              <TextInput
                label="Rate per page (Rs.)"
                value={draft.papers[p]!.rate}
                onChange={(e) => update((d) => void (d.papers[p]!.rate = e.target.value))}
              />
              {draft.papers[p]!.brackets.map((b, i) => (
                <div key={i} className="grid grid-cols-[1fr_1fr_auto] items-end gap-2">
                  <TextInput
                    label="From printed pages"
                    inputMode="numeric"
                    value={b.min}
                    onChange={(e) =>
                      update((d) => void (d.papers[p]!.brackets[i]!.min = e.target.value))
                    }
                  />
                  <TextInput
                    label="Rate (Rs.)"
                    value={b.rate}
                    onChange={(e) =>
                      update((d) => void (d.papers[p]!.brackets[i]!.rate = e.target.value))
                    }
                  />
                  <Button
                    variant="ghost"
                    aria-label="Remove bracket"
                    onClick={() => update((d) => void d.papers[p]!.brackets.splice(i, 1))}
                  >
                    ✕
                  </Button>
                </div>
              ))}
              <Button
                variant="ghost"
                onClick={() =>
                  update((d) => void d.papers[p]!.brackets.push({ min: "", rate: "" }))
                }
              >
                + Volume bracket
              </Button>
            </fieldset>
          ))}
          {BINDINGS.map((b) => (
            <fieldset key={b} className="space-y-2 rounded border border-slate-200 p-3">
              <legend className="px-1 text-sm font-medium">{humanize(b)}</legend>
              <TextInput
                label="Fee per copy (Rs.)"
                value={draft.bindings[b]!.fee}
                onChange={(e) => update((d) => void (d.bindings[b]!.fee = e.target.value))}
              />
              <TextInput
                label="Maximum pages (blank for none)"
                inputMode="numeric"
                value={draft.bindings[b]!.max}
                onChange={(e) => update((d) => void (d.bindings[b]!.max = e.target.value))}
              />
            </fieldset>
          ))}
          <fieldset className="space-y-2 rounded border border-slate-200 p-3">
            <legend className="px-1 text-sm font-medium">Delivery fee per zone</legend>
            {draft.zones.map((z, i) => (
              <div key={i} className="grid grid-cols-[6rem_1fr_auto] items-end gap-2">
                <TextInput
                  label="Zone"
                  value={z.zone}
                  onChange={(e) => update((d) => void (d.zones[i]!.zone = e.target.value))}
                />
                <TextInput
                  label="Fee (Rs.)"
                  value={z.fee}
                  onChange={(e) => update((d) => void (d.zones[i]!.fee = e.target.value))}
                />
                <Button
                  variant="ghost"
                  aria-label="Remove zone"
                  onClick={() => update((d) => void d.zones.splice(i, 1))}
                >
                  ✕
                </Button>
              </div>
            ))}
            <Button
              variant="ghost"
              onClick={() => update((d) => void d.zones.push({ zone: "", fee: "" }))}
            >
              + Zone
            </Button>
          </fieldset>
          <fieldset className="space-y-2 rounded border border-slate-200 p-3">
            <legend className="px-1 text-sm font-medium">Other</legend>
            <TextInput
              label="COD fee (Rs.)"
              value={draft.cod}
              onChange={(e) => update((d) => void (d.cod = e.target.value))}
            />
            <TextInput
              label="Maximum copies per order"
              inputMode="numeric"
              value={draft.maxCopies}
              onChange={(e) => update((d) => void (d.maxCopies = e.target.value))}
            />
          </fieldset>
        </div>
        <TextInput
          label="Effective from"
          type="datetime-local"
          required
          value={effectiveFrom}
          onChange={(e) => setEffectiveFrom(e.target.value)}
        />
        <TextArea label="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
        <div className="flex gap-2">
          <Button type="submit" busy={save.isPending}>
            Save new version
          </Button>
          <Button variant="ghost" onClick={onDone}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}
