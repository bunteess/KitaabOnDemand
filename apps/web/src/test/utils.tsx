import { QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router";
import { mockFetch, mockSignIn, resetMock } from "../api/mock";
import { tokens } from "../api/tokens";
import { createQueryClient, routes } from "../App";
import { AuthProvider } from "../auth/AuthContext";

/** Renders the whole portal at `path` against the in-memory mock API. */
export function renderApp(path: string, { as }: { as?: "ADMIN" | "VENDOR" } = {}) {
  vi.stubGlobal("fetch", mockFetch);
  resetMock();
  tokens.clear();
  if (as) {
    const pair = mockSignIn(as);
    tokens.save(pair.access_token, pair.refresh_token);
  }
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const client = createQueryClient();
  client.setDefaultOptions({ queries: { retry: false } });
  render(
    <QueryClientProvider client={client}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  );
  return router;
}
