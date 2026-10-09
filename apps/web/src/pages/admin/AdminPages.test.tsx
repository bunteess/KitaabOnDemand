import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "../../test/utils";
import { fromDraft } from "./PricingPage";

test("vendors: add a vendor and create a login", async () => {
  const user = userEvent.setup();
  renderApp("/admin/vendors", { as: "ADMIN" });
  await user.click(await screen.findByRole("button", { name: "Add vendor" }));
  const dialog = await screen.findByRole("dialog", { name: "Add vendor" });
  await user.type(within(dialog).getByLabelText("Name"), "Peshawar Press");
  await user.type(within(dialog).getByLabelText("Contact name"), "Imran");
  await user.type(within(dialog).getByLabelText("Contact phone"), "03451234567");
  await user.click(within(dialog).getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Peshawar Press")).toBeInTheDocument();

  const row = screen.getByText("Peshawar Press").closest("tr")!;
  await user.click(within(row).getByRole("button", { name: "Logins" }));
  const logins = await screen.findByRole("dialog", { name: "Peshawar Press: logins" });
  expect(await within(logins).findByText("No logins yet.")).toBeInTheDocument();
  await user.type(within(logins).getByLabelText("Email"), "imran@example.com");
  await user.type(within(logins).getByLabelText("Full name"), "Imran Khan");
  await user.click(within(logins).getByRole("button", { name: "Create login" }));
  expect(await screen.findByText("Temp-7g4K-29xQ")).toBeInTheDocument();
});

test("vendors: edit an existing vendor", async () => {
  const user = userEvent.setup();
  renderApp("/admin/vendors", { as: "ADMIN" });
  const row = (await screen.findByText("Karachi Binders")).closest("tr")!;
  await user.click(within(row).getByRole("button", { name: "Edit" }));
  const dialog = await screen.findByRole("dialog", { name: "Edit vendor" });
  const name = within(dialog).getByLabelText("Name");
  await user.clear(name);
  await user.type(name, "Karachi Binders Ltd");
  await user.click(within(dialog).getByRole("checkbox", { name: "Active" }));
  await user.click(within(dialog).getByRole("button", { name: "Save" }));
  expect(await screen.findByText("Karachi Binders Ltd")).toBeInTheDocument();
});

test("admins: create an admin shows the authenticator link once", async () => {
  const user = userEvent.setup();
  renderApp("/admin/staff", { as: "ADMIN" });
  expect(await screen.findByText("admin@example.com")).toBeInTheDocument();
  await user.type(screen.getByLabelText("Email"), "second@example.com");
  await user.type(screen.getByLabelText("Full name"), "Second Admin");
  await user.click(screen.getByRole("button", { name: "Create admin" }));
  expect(await screen.findByText(/otpauth:\/\/totp/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Done" }));
  const row = (await screen.findByText("second@example.com")).closest("tr")!;
  await user.click(within(row).getByRole("button", { name: "Deactivate" }));
  expect(await within(row).findByText("Inactive")).toBeInTheDocument();
});

test("customers: search and open a customer", async () => {
  const user = userEvent.setup();
  const router = renderApp("/admin/customers", { as: "ADMIN" });
  await user.type(await screen.findByLabelText("Search"), "Ayesha");
  await user.click(screen.getByRole("button", { name: "Search" }));
  await user.click(await screen.findByText("Ayesha Khan"));
  await waitFor(() => expect(router.state.location.pathname).toBe("/admin/customers/cust-1"));
  expect(await screen.findByText("+923001234567")).toBeInTheDocument();
  await user.click(screen.getByText("KD9PLACED"));
  await waitFor(() => expect(router.state.location.pathname).toMatch(/\/admin\/orders\//));
});

test("pricing: save a new version with a changed rate", async () => {
  const user = userEvent.setup();
  renderApp("/admin/pricing", { as: "ADMIN" });
  await user.click(await screen.findByRole("button", { name: "New version" }));
  const [rate] = screen.getAllByLabelText("Rate per page (Rs.)");
  await user.clear(rate!);
  await user.type(rate!, "2.25");
  await user.click(screen.getByRole("button", { name: "+ Zone" }));
  const zones = screen.getAllByLabelText("Zone");
  await user.type(zones.at(-1)!, "Z4");
  const fees = screen.getAllByLabelText("Fee (Rs.)");
  await user.type(fees.at(-1)!, "400");
  await user.type(screen.getByLabelText("Notes"), "October rates");
  await user.click(screen.getByRole("button", { name: "Save new version" }));
  expect(await screen.findByText("v2 (active)")).toBeInTheDocument();
  expect(screen.getByText(/Local white: Rs\. 2\.25/)).toBeInTheDocument();
  expect(screen.getByText("Zone Z4: Rs. 400")).toBeInTheDocument();
});

test("pricing: invalid amounts are caught before saving", async () => {
  const user = userEvent.setup();
  renderApp("/admin/pricing", { as: "ADMIN" });
  await user.click(await screen.findByRole("button", { name: "New version" }));
  const cod = screen.getByLabelText("COD fee (Rs.)");
  await user.clear(cod);
  await user.type(cod, "fifty");
  await user.click(screen.getByRole("button", { name: "Save new version" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("COD fee: enter an amount like 2.50");
});

test("fromDraft converts rupees to paisa", () => {
  const rules = fromDraft({
    papers: {
      LOCAL_WHITE: { rate: "2", brackets: [{ min: "1000", rate: "1.80" }] },
      IMPORTED_YELLOW: { rate: "2.75", brackets: [] },
    },
    bindings: {
      SOFTCOVER_PAPERBACK: { fee: "150", max: "800" },
      PREMIUM_HARDCOVER: { fee: "500", max: "" },
    },
    zones: [{ zone: "Z1", fee: "200" }],
    cod: "50",
    maxCopies: "20",
  });
  expect(rules).toMatchObject({
    papers: {
      LOCAL_WHITE: {
        rate_per_page_paisa: 200,
        brackets: [{ min_printed_pages: 1000, rate_per_page_paisa: 180 }],
      },
    },
    bindings: { PREMIUM_HARDCOVER: { fee_paisa: 50000, max_pages: null } },
    delivery_fees_paisa: { Z1: 20000 },
    cod_fee_paisa: 5000,
    max_copies: 20,
  });
});

test("cities: add a city and warn about a zone without a fee", async () => {
  const user = userEvent.setup();
  renderApp("/admin/cities", { as: "ADMIN" });
  await user.click(await screen.findByRole("button", { name: "Add city" }));
  const dialog = await screen.findByRole("dialog", { name: "Add city" });
  await user.type(within(dialog).getByLabelText("Name"), "Gilgit");
  await user.type(within(dialog).getByLabelText("Province"), "Gilgit-Baltistan");
  await user.type(within(dialog).getByLabelText("Courier zone code"), "Z9");
  await user.click(within(dialog).getByRole("button", { name: "Save" }));
  const row = (await screen.findByText("Gilgit")).closest("tr")!;
  expect(within(row).getByText("no delivery fee for this zone")).toBeInTheDocument();
});

test("settings: set a COD limit", async () => {
  const user = userEvent.setup();
  renderApp("/admin/settings", { as: "ADMIN" });
  const limit = await screen.findByLabelText("Cash on delivery limit (Rs.)");
  await user.type(limit, "abc");
  expect(screen.getByRole("button", { name: "Save settings" })).toBeDisabled();
  await user.clear(limit);
  await user.type(limit, "15000");
  await user.click(screen.getByRole("button", { name: "Save settings" }));
  expect(await screen.findByText("Saved.")).toBeInTheDocument();
});

test("audit log lists and filters entries", async () => {
  const user = userEvent.setup();
  renderApp("/admin/audit", { as: "ADMIN" });
  expect(await screen.findByText("file.download")).toBeInTheDocument();
  await user.type(screen.getByLabelText("Action"), "pricing.create");
  await user.click(screen.getByRole("button", { name: "Filter" }));
  expect(await screen.findByText("pricing.create")).toBeInTheDocument();
});

test("sign out returns to the login page", async () => {
  const user = userEvent.setup();
  const router = renderApp("/admin", { as: "ADMIN" });
  await user.click(await screen.findByRole("button", { name: "Sign out" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
});
