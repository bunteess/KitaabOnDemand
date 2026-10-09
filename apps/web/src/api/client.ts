import createClient, { type Middleware } from "openapi-fetch";
import type { components, paths } from "./schema";
import { tokens } from "./tokens";

export type Schemas = components["schemas"];
export type Problem = Schemas["Problem"];

/** Thrown for every non-2xx response. Screens switch on `code`. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly problem: Partial<Problem>;

  constructor(status: number, problem: Partial<Problem>) {
    super(problem.detail ?? problem.title ?? `Request failed (${status})`);
    this.status = status;
    this.code = problem.code ?? "error";
    this.problem = problem;
  }

  fieldErrors(): Record<string, string> {
    return Object.fromEntries((this.problem.errors ?? []).map((e) => [e.field, e.message]));
  }
}

// The mock API is a separate chunk, loaded only when VITE_MOCK_API=true.
const useMock = import.meta.env.VITE_MOCK_API === "true";
const fetchImpl: typeof fetch = useMock
  ? async (input, init) => (await import("./mock")).mockFetch(input, init)
  : (input, init) => globalThis.fetch(input, init);

let onSessionExpired: () => void = () => {};
export function setSessionExpiredHandler(handler: () => void) {
  onSessionExpired = handler;
}

let refreshing: Promise<boolean> | null = null;

async function refreshTokens(): Promise<boolean> {
  const refresh = tokens.refresh();
  if (!refresh) return false;
  const response = await fetchImpl(
    new Request(new URL("/api/v1/auth/refresh", window.location.origin), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    }),
  );
  if (!response.ok) {
    tokens.clear();
    return false;
  }
  const pair = (await response.json()) as Schemas["TokenPair"];
  tokens.save(pair.access_token, pair.refresh_token);
  return true;
}

const auth: Middleware = {
  onRequest({ request }) {
    const access = tokens.access();
    if (access && !request.url.includes("/auth/"))
      request.headers.set("Authorization", `Bearer ${access}`);
    return request;
  },
};

/** Retries a request once after refreshing the access token. */
async function fetchWithRefresh(input: Request): Promise<Response> {
  const retryCopy = input.clone();
  const response = await fetchImpl(input);
  if (response.status !== 401 || input.url.includes("/auth/")) return response;
  refreshing ??= refreshTokens().finally(() => (refreshing = null));
  if (!(await refreshing)) {
    onSessionExpired();
    return response;
  }
  retryCopy.headers.set("Authorization", `Bearer ${tokens.access()}`);
  return fetchImpl(retryCopy);
}

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  fetch: fetchWithRefresh,
});
api.use(auth);

/** Unwraps an openapi-fetch result or throws an ApiError. */
export async function unwrap<T>(
  promise: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await promise;
  if (!response.ok) throw new ApiError(response.status, (error ?? {}) as Partial<Problem>);
  return data as T;
}

/** Fetches a file (PDF, CSV) with the auth header and saves it. */
export async function download(path: string, filename: string): Promise<void> {
  const request = new Request(new URL(path, window.location.origin));
  const access = tokens.access();
  if (access) request.headers.set("Authorization", `Bearer ${access}`);
  const response = await fetchWithRefresh(request);
  if (!response.ok) {
    const problem = (await response.json().catch(() => ({}))) as Partial<Problem>;
    throw new ApiError(response.status, problem);
  }
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) return "Cannot reach the server. Check your connection.";
  return "Something went wrong.";
}
