import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "../../test/utils";

test("admin verifies and approves a PRINT order with a vendor", async () => {
  const user = userEvent.setup();
  renderApp("/admin", { as: "ADMIN" });
  await user.click(await screen.findByText("KD9PLACED"));

  expect(await screen.findByRole("heading", { name: "KD9PLACED" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Start verification" }));

  const approve = await screen.findByText("Approve and assign", { selector: "p" });
  const form = approve.closest("form")!;
  await within(form).findByRole("option", { name: "Lahore Print House" });
  await user.selectOptions(within(form).getByLabelText("Vendor"), "Lahore Print House");
  await user.type(within(form).getByLabelText("Agreed vendor cost (Rs.)"), "300");
  await user.click(within(form).getByRole("button", { name: "Approve and assign" }));

  expect(await screen.findByText(/Lahore Print House \(cost Rs\. 300\)/)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Mark printing (for vendor)" })).toBeInTheDocument();
});

test("reject requires a reason", async () => {
  const user = userEvent.setup();
  renderApp("/admin", { as: "ADMIN" });
  await user.click(await screen.findByText("KD4VERIFY"));
  await user.click(await screen.findByRole("button", { name: "Reject" }));
  const submit = screen.getAllByRole("button", { name: "Reject" }).at(-1)!;
  expect(submit).toBeDisabled();
  await user.type(screen.getByLabelText("Reject: reason"), "The PDF is blurry");
  await user.click(submit);
  expect(await screen.findAllByText(/The PDF is blurry/)).not.toHaveLength(0);
  expect(screen.queryByRole("button", { name: "Start verification" })).not.toBeInTheDocument();
});

test("admin previews and sends a SOURCE quote", async () => {
  const user = userEvent.setup();
  renderApp("/admin", { as: "ADMIN" });
  await user.click(await screen.findByRole("tab", { name: "To quote" }));
  await user.click(await screen.findByText("KD5REQST"));
  await user.type(await screen.findByLabelText("Pages"), "300");
  await user.type(screen.getByLabelText("Sourcing cost (Rs.)"), "500");
  await user.click(screen.getByRole("button", { name: "Preview price" }));
  const preview = await screen.findByTestId("quote-preview");
  expect(preview).toHaveTextContent("Online: Rs. 1,450");
  await user.click(screen.getByRole("button", { name: "Send quote" }));
  expect(await screen.findByRole("heading", { name: "Quotes" })).toBeInTheDocument();
});
