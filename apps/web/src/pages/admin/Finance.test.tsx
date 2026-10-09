import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "../../test/utils";

test("revenue shows totals by method", async () => {
  renderApp("/admin/finance/revenue", { as: "ADMIN" });
  expect(await screen.findByText("Rs. 5,480")).toBeInTheDocument();
  expect(screen.getByText("EASYPAISA")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Export CSV" })).toBeInTheDocument();
});

test("COD: mark selected orders remitted", async () => {
  const user = userEvent.setup();
  renderApp("/admin/finance/cod", { as: "ADMIN" });
  expect(await screen.findByText("Mock Courier: Rs. 1,860")).toBeInTheDocument();
  const button = screen.getByRole("button", { name: /Mark Rs\. 0 remitted/ });
  expect(button).toBeDisabled();
  await user.click(screen.getByRole("checkbox", { name: "Select KD1DELIV" }));
  await user.type(screen.getByLabelText("Remittance reference"), "TRAX-REM-881");
  await user.click(screen.getByRole("button", { name: "Mark Rs. 960 remitted" }));
  expect(await screen.findByText("Mock Courier: Rs. 900")).toBeInTheDocument();
});

test("payouts: create a batch and mark it paid", async () => {
  const user = userEvent.setup();
  renderApp("/admin/finance/payouts", { as: "ADMIN" });
  const row = (await screen.findByText("Lahore Print House")).closest("tr")!;
  await user.click(within(row).getByRole("button", { name: "Create batch" }));
  const batch = await screen.findByText("Lahore Print House: Rs. 600 · OPEN");
  const card = batch.closest("section")!;
  await user.type(within(card).getByLabelText("Payment reference"), "IBFT-2291");
  await user.click(within(card).getByRole("button", { name: "Mark paid" }));
  expect(await screen.findByText("Lahore Print House: Rs. 600 · PAID")).toBeInTheDocument();
});

test("refunds: record the gateway reference", async () => {
  const user = userEvent.setup();
  renderApp("/admin/finance/refunds", { as: "ADMIN" });
  expect(await screen.findByText("Customer cancelled")).toBeInTheDocument();
  await user.type(screen.getByLabelText("Reference"), "EP-REF-77");
  await user.click(screen.getByRole("button", { name: "Mark done" }));
  expect(await screen.findByText("No refunds")).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Status"), "PROCESSED");
  expect(await screen.findByText("EP-REF-77")).toBeInTheDocument();
});
