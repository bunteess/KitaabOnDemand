import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "../../test/utils";

test("vendor sees only assigned orders and moves one forward", async () => {
  const user = userEvent.setup();
  renderApp("/vendor", { as: "VENDOR" });
  expect(await screen.findByText("KD7ASSIGN")).toBeInTheDocument();
  expect(screen.queryByText("KD9PLACED")).not.toBeInTheDocument();

  await user.click(screen.getByText("KD7ASSIGN"));
  await user.click(await screen.findByRole("button", { name: "Start printing" }));
  await user.click(await screen.findByRole("button", { name: "Ready for dispatch" }));
  expect(await screen.findByText("Ready for dispatch", { selector: "span" })).toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "Start printing" })).not.toBeInTheDocument();
});
