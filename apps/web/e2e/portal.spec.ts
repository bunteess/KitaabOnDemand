import { expect, test, type Page } from "@playwright/test";
import {
  ADMIN,
  DEMO_VENDOR_NAME,
  VENDOR,
  courierEvent,
  placePrintOrder,
  requestBook,
  signUpCustomer,
  totpCode,
  type CreatedOrder,
} from "./support/api";

// One customer's orders move through the portal, admin and vendor taking turns.
test.describe.configure({ mode: "serial" });

let printOrder: CreatedOrder;
let bookOrder: CreatedOrder;
let cn = "";
// One signed-in page per role for the whole run: staff sign-in is rate-limited
// per address, and each login costs a TOTP code.
let admin: Page;
let vendor: Page;

test.beforeAll(async ({ browser, request }) => {
  const customer = await signUpCustomer(request);
  printOrder = await placePrintOrder(request, customer, 24);
  bookOrder = await requestBook(request, customer, `Raakh ${Date.now()}`);
  admin = await (await browser.newContext()).newPage();
  await signInAsAdmin(admin);
  vendor = await (await browser.newContext()).newPage();
  await signInAsVendor(vendor);
});

test.afterAll(async () => {
  await admin.context().close();
  await vendor.context().close();
});

async function signInAsAdmin(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(ADMIN.email);
  await page.getByLabel("Password").fill(ADMIN.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  // The server asks for the authenticator code after the password.
  await page.getByLabel("Authenticator code").fill(totpCode(ADMIN.totpSecret));
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/admin$/);
}

async function signInAsVendor(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(VENDOR.email);
  await page.getByLabel("Password").fill(VENDOR.password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\/vendor$/);
}

async function openAdminOrder(page: Page, order: CreatedOrder) {
  await page.goto("/admin");
  await page.getByLabel("Search").fill(order.code);
  await page.getByRole("button", { name: "Search" }).click();
  await page.getByText(order.code).click();
  await expect(page.getByRole("heading", { name: order.code })).toBeVisible();
}

const actions = (page: Page) =>
  page
    .locator("section, div")
    .filter({ hasText: /^Actions/ })
    .first();

test("admin reviews the file and assigns a vendor", async () => {
  const page = admin;
  await openAdminOrder(page, printOrder);
  await expect(page.getByText("Placed", { exact: true }).first()).toBeVisible();

  await page.getByRole("button", { name: "Start verification" }).click();
  await expect(page.getByText("Verifying", { exact: true }).first()).toBeVisible();

  // The PDF comes from a short-lived signed storage link, saved under the order code.
  const fileResponse = page
    .context()
    .waitForEvent("response", (r) => r.url().includes("X-Amz-Signature"));
  await page.getByRole("button", { name: "Open PDF" }).click();
  const file = await fileResponse;
  expect(file.status()).toBe(200);
  expect(file.headers()["content-type"]).toBe("application/pdf");
  expect(file.headers()["content-disposition"]).toContain(`${printOrder.code}.pdf`);

  await page.getByLabel("Vendor", { exact: true }).selectOption({ label: DEMO_VENDOR_NAME });
  await page.getByLabel("Agreed vendor cost (Rs.)").fill("300");
  await page.getByRole("button", { name: "Approve and assign" }).click();
  await expect(page.getByText("Assigned", { exact: true }).first()).toBeVisible();
  await expect(actions(page)).not.toContainText("Approve and assign");
});

test("the vendor prints the order", async () => {
  const page = vendor;
  await page.goto("/vendor");
  await expect(page.getByText(printOrder.code)).toBeVisible();
  await page.getByText(printOrder.code).click();
  // Vendors see the cash to collect, never the customer's price breakdown.
  await expect(page.getByRole("heading", { name: printOrder.code })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Price" })).toHaveCount(0);

  const slip = page.waitForEvent("download");
  await page.getByRole("button", { name: "Packing slip" }).click();
  expect((await slip).suggestedFilename()).toBe(`packing-slip-${printOrder.code}.pdf`);

  await page.getByRole("button", { name: "Start printing" }).click();
  await expect(page.getByText("In print", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Ready for dispatch" }).click();
  await expect(page.getByText("Ready for dispatch", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Ready for dispatch" })).toHaveCount(0);
});

test("admin dispatches with the courier and delivery comes back by webhook", async ({
  request,
}) => {
  const page = admin;
  await openAdminOrder(page, printOrder);
  await page.getByLabel("Courier").selectOption({ label: "Mock Courier" });
  await page.getByRole("button", { name: "Book courier and dispatch" }).click();
  await expect(page.getByText("Dispatched", { exact: true }).first()).toBeVisible();
  cn = (await page.getByText(/^MOCK-\d{6}$/).textContent()) ?? "";
  expect(cn).toMatch(/^MOCK-\d{6}$/);

  await courierEvent(request, cn, "DELIVERED");
  await expect(async () => {
    await page.reload();
    await expect(page.getByText("Delivered", { exact: true }).first()).toBeVisible({
      timeout: 2_000,
    });
  }).toPass({ timeout: 20_000 });
});

test("admin records the courier's cash and the order completes", async () => {
  const page = admin;
  await page.getByRole("link", { name: "COD pending" }).click();
  await expect(page.getByText(printOrder.code)).toBeVisible();
  await page.getByLabel(`Select ${printOrder.code}`).check();
  await page.getByLabel("Remittance reference").first().fill(`REMIT-${Date.now()}`);
  await page
    .getByRole("button", { name: /remitted/ })
    .first()
    .click();
  await expect(page.getByText(printOrder.code)).toHaveCount(0);

  await openAdminOrder(page, printOrder);
  await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible();
});

test("admin sends a quote for a book request", async () => {
  const page = admin;
  await openAdminOrder(page, bookOrder);
  await expect(page.getByText("Requested", { exact: true }).first()).toBeVisible();
  await page.getByLabel("Pages").fill("380");
  await page.getByLabel("Sourcing cost (Rs.)").fill("650");
  await page.getByRole("button", { name: "Preview price" }).click();
  await expect(page.getByText(/Online: Rs\./)).toBeVisible();
  await page.getByRole("button", { name: "Send quote" }).click();
  await expect(page.getByText("Quoted", { exact: true }).first()).toBeVisible();
});

test("vendor cannot open admin pages", async () => {
  await vendor.goto("/admin");
  await expect(vendor).toHaveURL(/\/vendor$/);
});

test("every admin page loads from the real API", async () => {
  const page = admin;
  for (const label of [
    "Vendors",
    "Customers",
    "Admins",
    "Pricing",
    "Cities",
    "Revenue",
    "COD pending",
    "Vendor payouts",
    "Refunds",
    "Audit log",
    "Settings",
  ]) {
    await page.getByRole("navigation", { name: "Main" }).getByRole("link", { name: label }).click();
    await expect(page.locator("main h1").first()).toBeVisible();
    await expect(page.getByRole("alert"), `${label} shows an error`).toHaveCount(0);
  }
});
