import { api, ApiError, errorMessage, setSessionExpiredHandler, unwrap } from "./client";
import { tokens } from "./tokens";

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const me = {
  id: "u",
  role: "ADMIN",
  full_name: "A",
  phone_e164: null,
  email: "a@x",
  phone_verified: false,
  terms_accepted: true,
  is_review_account: false,
  vendor_id: null,
  created_at: "2026-10-01T00:00:00Z",
};

afterEach(() => {
  tokens.clear();
  vi.unstubAllGlobals();
});

test("refreshes the access token once on 401 and retries", async () => {
  tokens.save("old-access", "refresh-1");
  const seen: string[] = [];
  vi.stubGlobal("fetch", async (request: Request) => {
    seen.push(
      `${request.method} ${new URL(request.url).pathname} ${request.headers.get("Authorization") ?? ""}`,
    );
    if (request.url.endsWith("/auth/refresh")) {
      return json(200, {
        access_token: "new-access",
        refresh_token: "refresh-2",
        token_type: "bearer",
        expires_in: 900,
        user: me,
      });
    }
    return request.headers.get("Authorization") === "Bearer new-access"
      ? json(200, me)
      : json(401, { code: "unauthorized", title: "Auth" });
  });
  const result = await unwrap(api.GET("/api/v1/me"));
  expect(result.email).toBe("a@x");
  expect(seen).toEqual([
    "GET /api/v1/me Bearer old-access",
    "POST /api/v1/auth/refresh ",
    "GET /api/v1/me Bearer new-access",
  ]);
  expect(tokens.refresh()).toBe("refresh-2");
});

test("expired sessions call the handler and surface the problem", async () => {
  tokens.save("old-access", "refresh-1");
  const expired = vi.fn();
  setSessionExpiredHandler(expired);
  vi.stubGlobal("fetch", async () =>
    json(401, { code: "unauthorized", title: "Authentication required" }),
  );
  await expect(unwrap(api.GET("/api/v1/me"))).rejects.toMatchObject({
    status: 401,
    code: "unauthorized",
  });
  expect(expired).toHaveBeenCalled();
  expect(tokens.refresh()).toBeNull();
});

test("errors carry the problem code and field errors", () => {
  const error = new ApiError(422, {
    code: "validation-error",
    title: "Invalid",
    errors: [{ field: "name", message: "Required" }],
  });
  expect(error.code).toBe("validation-error");
  expect(error.fieldErrors()).toEqual({ name: "Required" });
  expect(errorMessage(error)).toBe("Invalid");
  expect(errorMessage(new TypeError("fetch failed"))).toMatch(/Cannot reach/);
  expect(errorMessage("x")).toBe("Something went wrong.");
});
