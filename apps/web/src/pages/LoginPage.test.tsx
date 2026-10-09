import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderApp } from "../test/utils";

test("admin signs in with password and authenticator code", async () => {
  const user = userEvent.setup();
  const router = renderApp("/login");
  await user.type(screen.getByLabelText("Email"), "admin@example.com");
  await user.type(screen.getByLabelText("Password"), "password");
  await user.click(screen.getByRole("button", { name: "Sign in" }));

  const code = await screen.findByLabelText("Authenticator code");
  await user.type(code, "123456");
  await user.click(screen.getByRole("button", { name: "Sign in" }));

  await waitFor(() => expect(router.state.location.pathname).toBe("/admin"));
  expect(await screen.findByRole("heading", { name: "Orders" })).toBeInTheDocument();
});

test("wrong password shows the server message", async () => {
  const user = userEvent.setup();
  renderApp("/login");
  await user.type(screen.getByLabelText("Email"), "admin@example.com");
  await user.type(screen.getByLabelText("Password"), "nope");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Wrong email or password");
});

test("vendors land on their print queue", async () => {
  const user = userEvent.setup();
  const router = renderApp("/login");
  await user.type(screen.getByLabelText("Email"), "vendor@example.com");
  await user.type(screen.getByLabelText("Password"), "password");
  await user.click(screen.getByRole("button", { name: "Sign in" }));
  await waitFor(() => expect(router.state.location.pathname).toBe("/vendor"));
});

test("protected routes redirect to sign-in", async () => {
  const router = renderApp("/admin/vendors");
  await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
});

test("a vendor cannot open the admin area", async () => {
  const router = renderApp("/admin", { as: "VENDOR" });
  await waitFor(() => expect(router.state.location.pathname).toBe("/vendor"));
});
