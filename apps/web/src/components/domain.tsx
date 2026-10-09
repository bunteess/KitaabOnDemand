import type { Schemas } from "../api/client";
import { formatPkr, humanize } from "../lib/format";
import { KeyValue } from "./ui";

const badgeColors: Record<string, string> = {
  PENDING_PAYMENT: "bg-amber-100 text-amber-900",
  PLACED: "bg-sky-100 text-sky-900",
  REQUESTED: "bg-sky-100 text-sky-900",
  VERIFYING: "bg-indigo-100 text-indigo-900",
  QUOTED: "bg-amber-100 text-amber-900",
  ACCEPTED: "bg-indigo-100 text-indigo-900",
  ASSIGNED: "bg-violet-100 text-violet-900",
  SOURCING: "bg-violet-100 text-violet-900",
  IN_PRINT: "bg-violet-100 text-violet-900",
  READY_FOR_DISPATCH: "bg-teal-100 text-teal-900",
  DISPATCHED: "bg-teal-100 text-teal-900",
  DELIVERED: "bg-green-100 text-green-900",
  COMPLETED: "bg-green-100 text-green-900",
};

export function StatusBadge({ status }: { status: string }) {
  const color = badgeColors[status] ?? "bg-red-100 text-red-900";
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap ${color}`}
    >
      {humanize(status)}
    </span>
  );
}

export const PAPERS: Schemas["Paper"][] = ["LOCAL_WHITE", "IMPORTED_YELLOW"];
export const BINDINGS: Schemas["Binding"][] = ["SOFTCOVER_PAPERBACK", "PREMIUM_HARDCOVER"];

export function PriceBreakdown({ price }: { price: Schemas["PriceBreakdown"] }) {
  const items: [string, string][] = price.goods_override
    ? [
        ["Goods (override)", formatPkr(price.goods_paisa)],
        ["Calculated goods", formatPkr(price.calculated_goods_paisa)],
      ]
    : [
        [
          `Printing (${price.printed_pages} pages × ${formatPkr(price.rate_per_page_paisa)})`,
          formatPkr(price.printing_paisa),
        ],
        [`Binding × ${price.copies}`, formatPkr(price.binding_paisa)],
        ...(price.sourcing_cost_paisa > 0
          ? [["Sourcing cost", formatPkr(price.sourcing_cost_paisa)] as [string, string]]
          : []),
        ...(price.rounding_paisa > 0
          ? [["Rounding", formatPkr(price.rounding_paisa)] as [string, string]]
          : []),
      ];
  items.push([`Delivery (${price.delivery_zone})`, formatPkr(price.delivery_paisa)]);
  if (price.cod_fee_paisa > 0) items.push(["COD fee", formatPkr(price.cod_fee_paisa)]);
  items.push(["Total", formatPkr(price.total_paisa)]);
  return <KeyValue items={items} />;
}
