/** Money is integer paisa. Matches the server's format_pkr and the shared vectors. */
export function formatPkr(paisa: number): string {
  const sign = paisa < 0 ? "-" : "";
  const abs = Math.abs(paisa);
  const rupees = Math.floor(abs / 100);
  const remainder = abs % 100;
  const grouped = rupees.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const fraction = remainder === 0 ? "" : `.${remainder.toString().padStart(2, "0")}`;
  return `${sign}Rs. ${grouped}${fraction}`;
}

/** "1,250" or "1,250.50" (rupees) to paisa. Returns null for invalid input. */
export function parseRupees(text: string): number | null {
  const cleaned = text.replace(/[,\s]/g, "").replace(/^Rs\.?/i, "");
  if (!/^\d+(\.\d{1,2})?$/.test(cleaned)) return null;
  const [whole = "0", fraction = ""] = cleaned.split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}

export function paisaToRupeesText(paisa: number): string {
  const rupees = Math.floor(paisa / 100);
  const remainder = paisa % 100;
  return remainder === 0 ? `${rupees}` : `${rupees}.${remainder.toString().padStart(2, "0")}`;
}

const dateTime = new Intl.DateTimeFormat("en-PK", {
  timeZone: "Asia/Karachi",
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "numeric",
  minute: "2-digit",
});

const dateOnly = new Intl.DateTimeFormat("en-PK", {
  timeZone: "Asia/Karachi",
  day: "numeric",
  month: "short",
  year: "numeric",
});

/** Times are stored in UTC and shown in Pakistan time. */
export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTime.format(new Date(iso)) : "—";
}

export function formatDate(iso: string | null | undefined): string {
  return iso ? dateOnly.format(new Date(iso)) : "—";
}

/** Today's date in Pakistan as YYYY-MM-DD. */
export function todayInPakistan(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Karachi" }).format(now);
}

export function humanize(code: string): string {
  const text = code.replace(/_/g, " ").toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}
