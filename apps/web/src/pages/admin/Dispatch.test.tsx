import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "../../test/utils";

test("dispatch books the courier and records the CN", async () => {
  const user = userEvent.setup();
  renderApp("/admin", { as: "ADMIN" });
  await user.click(await screen.findByRole("tab", { name: "Ready to dispatch" }));
  await user.click(await screen.findByText("KD2READY"));
  const heading = await screen.findByText("Dispatch", { selector: "p" });
  const form = heading.closest("form")!;
  await within(form).findByRole("option", { name: "Mock Courier" });
  await user.selectOptions(within(form).getByLabelText("Courier"), "mock");
  await user.click(within(form).getByRole("button", { name: "Book courier and dispatch" }));
  expect(await screen.findByRole("heading", { name: "Shipment" })).toBeInTheDocument();
  expect(screen.getByText(/^MOCK-\d{6}$/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Mark delivered" }));
  expect(await screen.findByText("No actions available in this state.")).toBeInTheDocument();
});

test("manual courier needs a CN number", async () => {
  const user = userEvent.setup();
  renderApp("/admin", { as: "ADMIN" });
  await user.click(await screen.findByRole("tab", { name: "Ready to dispatch" }));
  await user.click(await screen.findByText("KD2READY"));
  const form = (await screen.findByText("Dispatch", { selector: "p" })).closest("form")!;
  await within(form).findByRole("option", { name: "Other courier (enter CN)" });
  await user.selectOptions(within(form).getByLabelText("Courier"), "manual");
  expect(within(form).getByLabelText("CN number")).toBeRequired();
  await user.type(within(form).getByLabelText("CN number"), "LEO-554433");
  await user.click(within(form).getByRole("button", { name: "Book courier and dispatch" }));
  expect(await screen.findByText("LEO-554433")).toBeInTheDocument();
});

test("start sourcing an accepted SOURCE order in-house", async () => {
  const user = userEvent.setup();
  renderApp("/admin", { as: "ADMIN" });
  await user.click(await screen.findByRole("tab", { name: "To source" }));
  await user.click(await screen.findByText("KD8ACCPT"));
  await user.click(await screen.findByRole("button", { name: "Start sourcing" }));
  expect(
    await screen.findByRole("button", { name: "Mark ready for dispatch" }),
  ).toBeInTheDocument();
});

test("orders list search and pagination controls", async () => {
  const user = userEvent.setup();
  renderApp("/admin?tab=6", { as: "ADMIN" });
  expect(await screen.findByText("6 total · page 1 of 1")).toBeInTheDocument();
  await user.type(screen.getByLabelText("Search"), "KD5");
  await user.click(screen.getByRole("button", { name: "Search" }));
  expect(await screen.findByText("1 total · page 1 of 1")).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("Type"), "PRINT");
  expect(await screen.findByText("No orders match these filters")).toBeInTheDocument();
});
