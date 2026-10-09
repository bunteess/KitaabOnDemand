import vectors from "../../../../packages/contracts/pricing_vectors.json";
import {
  formatDateTime,
  formatPkr,
  humanize,
  paisaToRupeesText,
  parseRupees,
  todayInPakistan,
} from "./format";

describe("formatPkr", () => {
  test.each(vectors.format_cases)("$paisa -> $text", ({ paisa, text }) => {
    expect(formatPkr(paisa)).toBe(text);
  });
});

describe("parseRupees", () => {
  test.each([
    ["1,250", 125000],
    ["1250.5", 125050],
    ["Rs. 99", 9900],
    ["0", 0],
  ])("%s", (input, expected) => expect(parseRupees(input)).toBe(expected));

  test.each(["", "abc", "1.234", "-5"])("rejects %s", (input) =>
    expect(parseRupees(input)).toBeNull(),
  );

  test("round-trips", () => expect(parseRupees(paisaToRupeesText(123456))).toBe(123456));
});

test("shows UTC times in Pakistan time", () => {
  expect(formatDateTime("2026-10-09T19:30:00Z")).toContain("10 Oct 2026");
  expect(todayInPakistan(new Date("2026-10-09T19:30:00Z"))).toBe("2026-10-10");
});

test("humanize", () => expect(humanize("READY_FOR_DISPATCH")).toBe("Ready for dispatch"));
