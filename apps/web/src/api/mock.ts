/**
 * An in-memory imitation of the admin and vendor API, used when the portal
 * runs with VITE_MOCK_API=true (clickable demo) and by component tests. It
 * follows packages/contracts/openapi.json but keeps only enough logic to
 * drive the screens. The real rules live in the backend.
 */
import type { components } from "./schema";

type S = components["schemas"];
type Json = Record<string, unknown>;

const now = () => new Date().toISOString();
const daysAgo = (days: number) => new Date(Date.now() - days * 86_400_000).toISOString();
let seq = 100;
const id = (prefix: string) => `${prefix}-${++seq}`;

const cities: S["CityAdminOut"][] = [
  {
    id: "city-khi",
    name: "Karachi",
    province: "Sindh",
    zone_code: "Z1",
    is_active: true,
    sort_order: 1,
  },
  {
    id: "city-lhe",
    name: "Lahore",
    province: "Punjab",
    zone_code: "Z1",
    is_active: true,
    sort_order: 2,
  },
  {
    id: "city-isb",
    name: "Islamabad",
    province: "Islamabad Capital Territory",
    zone_code: "Z2",
    is_active: true,
    sort_order: 3,
  },
];

const vendors: S["VendorOut"][] = [
  {
    id: "vendor-1",
    name: "Lahore Print House",
    contact_name: "Bilal Ahmed",
    contact_phone_e164: "+923211234567",
    email: "print@example.com",
    city_id: "city-lhe",
    address: "Urdu Bazaar, Lahore",
    is_active: true,
    created_at: daysAgo(30),
  },
  {
    id: "vendor-2",
    name: "Karachi Binders",
    contact_name: "Sana Malik",
    contact_phone_e164: "+923331234567",
    email: null,
    city_id: "city-khi",
    address: null,
    is_active: true,
    created_at: daysAgo(20),
  },
];

const staff: S["StaffUserOut"][] = [
  {
    id: "admin-1",
    role: "ADMIN",
    email: "admin@example.com",
    full_name: "Admin One",
    vendor_id: null,
    is_active: true,
    locked: false,
    last_login_at: now(),
  },
  {
    id: "vendor-user-1",
    role: "VENDOR",
    email: "vendor@example.com",
    full_name: "Bilal Ahmed",
    vendor_id: "vendor-1",
    is_active: true,
    locked: false,
    last_login_at: daysAgo(1),
  },
];

const rules: S["PricingRules"] = {
  papers: {
    LOCAL_WHITE: {
      rate_per_page_paisa: 200,
      brackets: [{ min_printed_pages: 2000, rate_per_page_paisa: 180 }],
    },
    IMPORTED_YELLOW: {
      rate_per_page_paisa: 275,
      brackets: [{ min_printed_pages: 2000, rate_per_page_paisa: 250 }],
    },
  },
  bindings: {
    SOFTCOVER_PAPERBACK: { fee_paisa: 15000, max_pages: 800 },
    PREMIUM_HARDCOVER: { fee_paisa: 50000, max_pages: 1200 },
  },
  delivery_fees_paisa: { Z1: 20000, Z2: 25000, Z3: 35000 },
  cod_fee_paisa: 5000,
  max_copies: 50,
};

const pricingVersions: S["PricingConfigVersion"][] = [
  {
    version: 1,
    effective_from: daysAgo(30),
    rules,
    notes: "Placeholder prices",
    created_by_name: "Seed",
    created_at: daysAgo(30),
    active: true,
  },
];

let settings: S["AppSettings"] = {
  cod_max_order_value_paisa: null,
  quote_validity_hours: 48,
  support_phone: "+920000000000",
  support_whatsapp: "+920000000000",
  support_email: "support@example.com",
  support_hours: "Mon to Sat, 10 am to 6 pm",
};

const shipping: S["ShippingOut"] = {
  recipient_name: "Ayesha Khan",
  recipient_phone_e164: "+923001234567",
  city_name: "Lahore",
  area: "Gulberg III",
  street_address: "House 12, Street 4, Block C",
  landmark: "Near Hafeez Centre",
};

function price(
  pages: number,
  copies: number,
  method: S["PaymentMethod"] | null,
  sourcing = 0,
): S["PriceBreakdown"] {
  const printed = pages * copies;
  const rate = printed >= 2000 ? 180 : 200;
  const printing = printed * rate;
  const binding = 15000 * copies;
  const before = printing + binding + sourcing;
  const goods = Math.ceil(before / 100) * 100;
  const cod = method === "COD" ? 5000 : 0;
  return {
    config_version: 1,
    pages,
    copies,
    paper: "LOCAL_WHITE",
    binding: "SOFTCOVER_PAPERBACK",
    printed_pages: printed,
    rate_per_page_paisa: rate,
    printing_paisa: printing,
    binding_paisa: binding,
    sourcing_cost_paisa: sourcing,
    goods_before_rounding_paisa: before,
    rounding_paisa: goods - before,
    calculated_goods_paisa: goods,
    goods_override: false,
    goods_paisa: goods,
    delivery_zone: "Z1",
    delivery_paisa: 20000,
    payment_method: method,
    cod_fee_paisa: cod,
    total_paisa: goods + 20000 + cod,
  };
}

const PRINT_STEPS = ["PLACED", "VERIFYING", "PRINTING", "OUT_FOR_DELIVERY", "COMPLETED"] as const;
const SOURCE_STEPS = ["PLACED", "VERIFYING", "OUT_FOR_DELIVERY", "COMPLETED"] as const;
const PRINT_STEP: Record<string, number> = {
  PLACED: 0,
  VERIFYING: 1,
  ASSIGNED: 1,
  IN_PRINT: 2,
  READY_FOR_DISPATCH: 2,
  DISPATCHED: 3,
  DELIVERED: 4,
  COMPLETED: 4,
};
const SOURCE_STEP: Record<string, number> = {
  REQUESTED: 0,
  QUOTED: 1,
  ACCEPTED: 1,
  SOURCING: 1,
  READY_FOR_DISPATCH: 1,
  DISPATCHED: 2,
  DELIVERED: 3,
  COMPLETED: 3,
};

interface MockOrder {
  detail: S["AdminOrderDetail"];
  vendorId: string | null;
}

function timeline(type: S["OrderType"], status: S["OrderStatus"]): S["TimelineEntry"][] {
  const steps = type === "PRINT" ? PRINT_STEPS : SOURCE_STEPS;
  const reached = (type === "PRINT" ? PRINT_STEP : SOURCE_STEP)[status] ?? 0;
  return steps.map((step, i) => ({
    step,
    state:
      i < reached || (i === reached && i === steps.length - 1)
        ? "DONE"
        : i === reached
          ? "CURRENT"
          : "UPCOMING",
    at: i <= reached ? daysAgo(2 - Math.min(i, 2)) : null,
  }));
}

const ACTIONS: Record<string, string[]> = {
  PLACED: ["start-verification", "cancel"],
  VERIFYING: ["approve", "reject", "cancel"],
  ASSIGNED: ["start-printing", "cancel"],
  IN_PRINT: ["ready-for-dispatch", "cancel"],
  READY_FOR_DISPATCH: ["dispatch"],
  DISPATCHED: ["mark-delivered", "mark-delivery-failed"],
  REQUESTED: ["quote", "mark-unavailable", "cancel"],
  QUOTED: ["cancel"],
  ACCEPTED: ["start-sourcing", "mark-unavailable", "cancel"],
  SOURCING: ["ready-for-dispatch", "mark-unavailable", "cancel"],
};

function makeOrder(init: {
  code: string;
  type: S["OrderType"];
  status: S["OrderStatus"];
  title: string;
  pages?: number;
  copies?: number;
  method?: S["PaymentMethod"];
  vendorId?: string | null;
  created: string;
}): MockOrder {
  const orderId = id("order");
  const p = init.pages ? price(init.pages, init.copies ?? 1, init.method ?? "COD") : null;
  const vendor = vendors.find((v) => v.id === init.vendorId) ?? null;
  const detail: S["AdminOrderDetail"] = {
    id: orderId,
    code: init.code,
    type: init.type,
    status: init.status,
    timeline: timeline(init.type, init.status),
    exit: null,
    awaiting_payment: init.status === "PENDING_PAYMENT",
    pages: init.pages ?? null,
    paper: p ? "LOCAL_WHITE" : null,
    binding: p ? "SOFTCOVER_PAPERBACK" : null,
    copies: init.copies ?? 1,
    upload:
      init.type === "PRINT"
        ? {
            id: id("upload"),
            status: "VALID",
            filename: init.title,
            size_bytes: 18_400_000,
            page_count: init.pages ?? null,
            client_page_count: init.pages ?? null,
            rejection_code: null,
            rejection_message: null,
            uploaded_parts: [],
            created_at: init.created,
            validated_at: init.created,
          }
        : null,
    book:
      init.type === "SOURCE"
        ? {
            title: init.title,
            author: "Umera Ahmed",
            isbn: null,
            edition: null,
            notes: "Urdu edition please",
            preferred_paper: null,
            preferred_binding: null,
          }
        : null,
    price: p,
    total_paisa: p?.total_paisa ?? null,
    payment: p
      ? {
          id: id("pay"),
          method: init.method ?? "COD",
          status: "PENDING",
          amount_paisa: p.total_paisa,
          checkout_url: null,
          paid_at: null,
        }
      : null,
    shipping,
    quote: null,
    tracking: null,
    can_cancel: true,
    created_at: init.created,
    updated_at: init.created,
    customer: {
      id: "cust-1",
      full_name: "Ayesha Khan",
      phone_e164: "+923001234567",
      is_review_account: false,
    },
    history: [
      {
        from_status: null,
        to_status: init.status,
        actor: "USER",
        actor_name: "Ayesha Khan",
        reason: null,
        created_at: init.created,
      },
    ],
    payments: [],
    refunds: [],
    quotes: [],
    admin_upload:
      init.type === "PRINT"
        ? {
            id: id("upload"),
            status: "VALID",
            filename: init.title,
            size_bytes: 18_400_000,
            page_count: init.pages ?? null,
            client_page_count: init.pages ?? null,
            sha256: "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
            file_available: true,
            purged_at: null,
          }
        : null,
    vendor: vendor ? { id: vendor.id, name: vendor.name } : null,
    vendor_cost_paisa: vendor ? 30000 : null,
    rejection_reason: null,
    cancel_reason: null,
    allowed_actions: ACTIONS[init.status] ?? [],
  };
  if (detail.payment) detail.payments = [detail.payment];
  return { detail, vendorId: init.vendorId ?? null };
}

const orders: MockOrder[] = [
  makeOrder({
    code: "KD9PLACED",
    type: "PRINT",
    status: "PLACED",
    title: "thesis-final.pdf",
    pages: 180,
    copies: 2,
    created: daysAgo(0),
  }),
  makeOrder({
    code: "KD4VERIFY",
    type: "PRINT",
    status: "VERIFYING",
    title: "class-notes.pdf",
    pages: 96,
    created: daysAgo(1),
  }),
  makeOrder({
    code: "KD7ASSIGN",
    type: "PRINT",
    status: "ASSIGNED",
    title: "novel-draft.pdf",
    pages: 320,
    vendorId: "vendor-1",
    created: daysAgo(2),
  }),
  makeOrder({
    code: "KD2READY",
    type: "PRINT",
    status: "READY_FOR_DISPATCH",
    title: "manual.pdf",
    pages: 60,
    vendorId: "vendor-1",
    created: daysAgo(3),
  }),
  makeOrder({
    code: "KD5REQST",
    type: "SOURCE",
    status: "REQUESTED",
    title: "Peer-e-Kamil",
    created: daysAgo(0),
  }),
  makeOrder({
    code: "KD8ACCPT",
    type: "SOURCE",
    status: "ACCEPTED",
    title: "Raja Gidh",
    pages: 520,
    method: "COD",
    created: daysAgo(2),
  }),
];

const auditLogs: S["AuditLogOut"][] = [
  {
    id: id("audit"),
    actor_name: "Admin One",
    actor_role: "ADMIN",
    action: "pricing.create",
    entity_type: "pricing_config",
    entity_id: "1",
    details: { version: 1 },
    created_at: daysAgo(30),
  },
  {
    id: id("audit"),
    actor_name: "Bilal Ahmed",
    actor_role: "VENDOR",
    action: "file.download",
    entity_type: "order",
    entity_id: orders[2]!.detail.id,
    details: {},
    created_at: daysAgo(1),
  },
];

let refunds: S["RefundOut"][] = [
  {
    id: id("refund"),
    order_id: orders[1]!.detail.id,
    order_code: "KD4VERIFY",
    amount_paisa: 42000,
    status: "PENDING",
    reason: "Customer cancelled",
    reference: null,
    created_at: daysAgo(1),
    processed_at: null,
  },
];

const codPending: S["CodPendingGroup"][] = [
  {
    courier_code: "mock",
    courier_name: "Mock Courier",
    total_paisa: 186000,
    orders: [
      {
        order_id: "o-x1",
        order_code: "KD1DELIV",
        cn_number: "MOCK-100231",
        amount_paisa: 96000,
        delivered_at: daysAgo(2),
      },
      {
        order_id: "o-x2",
        order_code: "KD3DELIV",
        cn_number: "MOCK-100245",
        amount_paisa: 90000,
        delivered_at: daysAgo(1),
      },
    ],
  },
];

let batches: S["PayoutBatchOut"][] = [];

const users: Record<string, S["MeOut"]> = {
  "admin@example.com": {
    id: "admin-1",
    role: "ADMIN",
    full_name: "Admin One",
    phone_e164: null,
    email: "admin@example.com",
    phone_verified: false,
    terms_accepted: true,
    is_review_account: false,
    vendor_id: null,
    created_at: daysAgo(60),
  },
  "vendor@example.com": {
    id: "vendor-user-1",
    role: "VENDOR",
    full_name: "Bilal Ahmed",
    phone_e164: null,
    email: "vendor@example.com",
    phone_verified: false,
    terms_accepted: true,
    is_review_account: false,
    vendor_id: "vendor-1",
    created_at: daysAgo(60),
  },
};
let signedIn: S["MeOut"] | null = null;

// -- plumbing ------------------------------------------------------------------

class Problem {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly title: string,
    readonly extra?: Json,
  ) {}
}

function json(status: number, body: unknown): Response {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": status >= 400 ? "application/problem+json" : "application/json" },
  });
}

function page<T>(items: T[], url: URL, pageSizeDefault = 25) {
  const p = Number(url.searchParams.get("page") ?? 1);
  const size = Number(url.searchParams.get("page_size") ?? pageSizeDefault);
  return {
    items: items.slice((p - 1) * size, p * size),
    total: items.length,
    page: p,
    page_size: size,
  };
}

function findOrder(orderId: string): MockOrder {
  const order = orders.find((o) => o.detail.id === orderId);
  if (!order) throw new Problem(404, "not-found", "Order not found");
  return order;
}

function move(order: MockOrder, to: S["OrderStatus"], reason: string | null = null) {
  const d = order.detail;
  d.history = [
    ...d.history,
    {
      from_status: d.status,
      to_status: to,
      actor: "ADMIN",
      actor_name: signedIn?.full_name ?? null,
      reason,
      created_at: now(),
    },
  ];
  d.status = to;
  d.updated_at = now();
  d.timeline = timeline(d.type, to);
  d.allowed_actions = ACTIONS[to] ?? [];
  const exits: S["OrderStatus"][] = ["REJECTED", "CANCELLED", "UNAVAILABLE", "DELIVERY_FAILED"];
  if (exits.includes(to)) d.exit = { status: to, reason, at: now() };
  if (to === "REJECTED") d.rejection_reason = reason;
  if (to === "CANCELLED") d.cancel_reason = reason;
  d.can_cancel = d.allowed_actions.includes("cancel");
}

function summary(o: MockOrder): S["AdminOrderSummary"] {
  const d = o.detail;
  return {
    id: d.id,
    code: d.code,
    type: d.type,
    status: d.status,
    title: d.book?.title ?? d.upload?.filename ?? d.code,
    customer_name: d.customer.full_name,
    customer_phone_masked: "+92300*****67",
    city_name: d.shipping.city_name,
    copies: d.copies,
    total_paisa: d.total_paisa,
    payment_method: d.payment?.method ?? null,
    payment_status: d.payment?.status ?? null,
    vendor_name: d.vendor?.name ?? null,
    is_review_account: d.customer.is_review_account,
    created_at: d.created_at,
    updated_at: d.updated_at,
  };
}

function vendorSummary(o: MockOrder): S["VendorOrderSummary"] {
  const d = o.detail;
  return {
    id: d.id,
    code: d.code,
    type: d.type,
    status: d.status,
    title: d.book?.title ?? d.upload?.filename ?? d.code,
    pages: d.pages,
    paper: d.paper,
    binding: d.binding,
    copies: d.copies,
    city_name: d.shipping.city_name,
    cod_amount_paisa: d.payment?.method === "COD" ? (d.total_paisa ?? 0) : 0,
    assigned_at: d.updated_at,
  };
}

function vendorDetail(o: MockOrder): S["VendorOrderDetail"] {
  const actions =
    o.detail.status === "ASSIGNED"
      ? ["start-printing"]
      : ["IN_PRINT", "SOURCING"].includes(o.detail.status)
        ? ["ready-for-dispatch"]
        : [];
  return {
    ...vendorSummary(o),
    shipping: o.detail.shipping,
    file_available: o.detail.type === "PRINT",
    cn_number: o.detail.tracking?.cn_number ?? null,
    allowed_actions: actions,
  };
}

function tokenPair(user: S["MeOut"]): S["TokenPair"] {
  signedIn = user;
  return {
    access_token: `mock-access-${user.id}`,
    refresh_token: `mock-refresh-${user.id}`,
    token_type: "bearer",
    expires_in: 900,
    user,
  };
}

const PDF_BYTES =
  "%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF";

function route(method: string, url: URL, body: Json): Response {
  const path = url.pathname.replace(/^\/api\/v1/, "");
  const parts = path.split("/").filter(Boolean);
  const is = (m: string, pattern: string) => {
    if (m !== method) return null;
    const segs = pattern.split("/").filter(Boolean);
    if (segs.length !== parts.length) return null;
    const params: Record<string, string> = {};
    for (let i = 0; i < segs.length; i++) {
      const seg = segs[i]!;
      if (seg.startsWith(":")) params[seg.slice(1)] = parts[i]!;
      else if (seg !== parts[i]) return null;
    }
    return params;
  };
  let p: Record<string, string> | null;

  if ((p = is("POST", "auth/staff/login"))) {
    const user = users[String(body.email).toLowerCase()];
    if (!user || body.password !== "password")
      throw new Problem(401, "invalid-credentials", "Wrong email or password");
    if (user.role === "ADMIN" && !body.totp_code)
      throw new Problem(401, "totp-required", "Enter the code from your authenticator app");
    if (user.role === "ADMIN" && body.totp_code !== "123456")
      throw new Problem(401, "totp-invalid", "That code is not right");
    return json(200, tokenPair(user));
  }
  if ((p = is("POST", "auth/refresh"))) {
    const user = Object.values(users).find((u) => String(body.refresh_token).endsWith(u.id));
    if (!user) throw new Problem(401, "invalid-token", "Session expired");
    return json(200, tokenPair(user));
  }
  if ((p = is("POST", "auth/logout"))) {
    signedIn = null;
    return json(204, null);
  }
  if (!signedIn) throw new Problem(401, "unauthorized", "Authentication required");
  if ((p = is("GET", "me"))) return json(200, signedIn);

  // -- vendor
  if (parts[0] === "vendor") {
    if (signedIn.role !== "VENDOR") throw new Problem(403, "forbidden", "Vendors only");
    const mine = orders.filter((o) => o.vendorId === signedIn?.vendor_id);
    if ((p = is("GET", "vendor/orders"))) return json(200, page(mine.map(vendorSummary), url));
    const own = (orderId: string) => {
      const o = mine.find((m) => m.detail.id === orderId);
      if (!o) throw new Problem(404, "not-found", "Order not found");
      return o;
    };
    if ((p = is("GET", "vendor/orders/:id"))) return json(200, vendorDetail(own(p.id!)));
    if ((p = is("GET", "vendor/orders/:id/file-url")))
      return json(200, {
        url: "data:application/pdf;base64,",
        expires_at: new Date(Date.now() + 300_000).toISOString(),
      });
    if ((p = is("GET", "vendor/orders/:id/packing-slip")))
      return new Response(PDF_BYTES, { headers: { "Content-Type": "application/pdf" } });
    if ((p = is("POST", "vendor/orders/:id/start-printing"))) {
      const o = own(p.id!);
      move(o, "IN_PRINT");
      return json(200, vendorDetail(o));
    }
    if ((p = is("POST", "vendor/orders/:id/ready-for-dispatch"))) {
      const o = own(p.id!);
      move(o, "READY_FOR_DISPATCH");
      return json(200, vendorDetail(o));
    }
  }

  if (parts[0] !== "admin") throw new Problem(404, "not-found", `No mock for ${method} ${path}`);
  if (signedIn.role !== "ADMIN") throw new Problem(403, "forbidden", "Admins only");

  // -- admin orders
  if ((p = is("GET", "admin/orders"))) {
    const type = url.searchParams.get("type");
    const statuses = url.searchParams.getAll("status");
    const q = url.searchParams.get("q")?.toLowerCase();
    const items = orders
      .filter((o) => !type || o.detail.type === type)
      .filter((o) => statuses.length === 0 || statuses.includes(o.detail.status))
      .filter(
        (o) =>
          !q ||
          o.detail.code.toLowerCase().includes(q) ||
          (o.detail.customer.full_name ?? "").toLowerCase().includes(q),
      )
      .map(summary);
    return json(200, page(items, url));
  }
  if ((p = is("GET", "admin/orders/:id"))) return json(200, findOrder(p.id!).detail);
  if ((p = is("GET", "admin/orders/:id/file-url")))
    return json(200, {
      url: "data:application/pdf;base64,",
      expires_at: new Date(Date.now() + 300_000).toISOString(),
    });
  if ((p = is("GET", "admin/orders/:id/packing-slip")))
    return new Response(PDF_BYTES, { headers: { "Content-Type": "application/pdf" } });
  const transitions: Record<string, S["OrderStatus"]> = {
    "start-verification": "VERIFYING",
    reject: "REJECTED",
    cancel: "CANCELLED",
    "mark-unavailable": "UNAVAILABLE",
    "start-printing": "IN_PRINT",
    "ready-for-dispatch": "READY_FOR_DISPATCH",
    "mark-delivered": "DELIVERED",
    "mark-delivery-failed": "DELIVERY_FAILED",
  };
  if (method === "POST" && parts[1] === "orders" && parts.length === 4 && transitions[parts[3]!]) {
    const o = findOrder(parts[2]!);
    move(o, transitions[parts[3]!]!, (body.reason as string | undefined) ?? null);
    return json(200, o.detail);
  }
  if ((p = is("POST", "admin/orders/:id/approve"))) {
    const o = findOrder(p.id!);
    const vendor = vendors.find((v) => v.id === body.vendor_id);
    if (!vendor) throw new Problem(422, "vendor-not-found", "Choose an active vendor");
    o.vendorId = vendor.id;
    o.detail.vendor = { id: vendor.id, name: vendor.name };
    o.detail.vendor_cost_paisa = Number(body.vendor_cost_paisa);
    move(o, "ASSIGNED");
    return json(200, o.detail);
  }
  if (
    (p = is("POST", "admin/orders/:id/quote/preview")) ||
    (p = is("POST", "admin/orders/:id/quote"))
  ) {
    const o = findOrder(p.id!);
    const b = price(
      Number(body.pages),
      Number(body.copies),
      null,
      Number(body.sourcing_cost_paisa),
    );
    if (body.goods_override_paisa != null) {
      b.goods_override = true;
      b.goods_paisa = Number(body.goods_override_paisa);
      b.total_paisa = b.goods_paisa + b.delivery_paisa;
    }
    const preview = {
      breakdown: b,
      total_if_digital_paisa: b.total_paisa,
      total_if_cod_paisa: b.total_paisa + 5000,
    };
    if (parts[4] === "preview") return json(200, preview);
    o.detail.quotes = [
      ...o.detail.quotes,
      {
        id: id("quote"),
        status: "OPEN",
        pages: b.pages,
        paper: b.paper,
        binding: b.binding,
        copies: b.copies,
        sourcing_cost_paisa: b.sourcing_cost_paisa,
        calculated_goods_paisa: b.calculated_goods_paisa,
        goods_paisa: b.goods_paisa,
        override_reason: (body.override_reason as string | undefined) ?? null,
        breakdown: b,
        valid_until: new Date(Date.now() + 48 * 3_600_000).toISOString(),
        created_by_name: signedIn.full_name,
        created_at: now(),
      },
    ];
    move(o, "QUOTED");
    return json(200, o.detail);
  }
  if ((p = is("POST", "admin/orders/:id/start-sourcing"))) {
    const o = findOrder(p.id!);
    if (body.vendor_id) {
      const vendor = vendors.find((v) => v.id === body.vendor_id)!;
      o.vendorId = vendor.id;
      o.detail.vendor = { id: vendor.id, name: vendor.name };
      o.detail.vendor_cost_paisa = Number(body.vendor_cost_paisa ?? 0);
    }
    move(o, "SOURCING");
    return json(200, o.detail);
  }
  if ((p = is("POST", "admin/orders/:id/dispatch"))) {
    const o = findOrder(p.id!);
    const cn =
      (body.cn_number as string | undefined) ||
      `MOCK-${Math.floor(100000 + Math.random() * 900000)}`;
    o.detail.tracking = {
      courier_code: String(body.courier_code),
      courier_name: "Mock Courier",
      cn_number: cn,
      tracking_url: `https://example.com/track/${cn}`,
      dispatched_at: now(),
      last_status: "Booked",
    };
    move(o, "DISPATCHED");
    return json(200, o.detail);
  }
  if ((p = is("POST", "admin/orders/:id/refunds"))) {
    const o = findOrder(p.id!);
    const refund: S["RefundOut"] = {
      id: id("refund"),
      order_id: o.detail.id,
      order_code: o.detail.code,
      amount_paisa: Number(body.amount_paisa),
      status: "PENDING",
      reason: String(body.reason),
      reference: null,
      created_at: now(),
      processed_at: null,
    };
    refunds = [refund, ...refunds];
    o.detail.refunds = [...o.detail.refunds, refund];
    return json(201, refund);
  }
  if ((p = is("GET", "admin/refunds"))) {
    const status = url.searchParams.get("status");
    return json(
      200,
      page(
        refunds.filter((r) => !status || r.status === status),
        url,
      ),
    );
  }
  if ((p = is("POST", "admin/refunds/:id/mark-processed"))) {
    const refund = refunds.find((r) => r.id === p!.id);
    if (!refund) throw new Problem(404, "not-found", "Refund not found");
    Object.assign(refund, { status: "PROCESSED", reference: body.reference, processed_at: now() });
    return json(200, refund);
  }
  if ((p = is("GET", "admin/couriers"))) {
    return json(200, [
      { code: "mock", name: "Mock Courier", has_api: true },
      { code: "manual", name: "Other courier (enter CN)", has_api: false },
    ]);
  }

  // -- people
  if ((p = is("GET", "admin/vendors"))) return json(200, vendors);
  if ((p = is("POST", "admin/vendors"))) {
    const v: S["VendorOut"] = {
      id: id("vendor"),
      name: String(body.name),
      contact_name: String(body.contact_name),
      contact_phone_e164: String(body.contact_phone),
      email: (body.email as string | null) ?? null,
      city_id: (body.city_id as string | null) ?? null,
      address: (body.address as string | null) ?? null,
      is_active: body.is_active !== false,
      created_at: now(),
    };
    vendors.push(v);
    return json(201, v);
  }
  if ((p = is("PUT", "admin/vendors/:id"))) {
    const v = vendors.find((x) => x.id === p!.id)!;
    Object.assign(v, { ...body, contact_phone_e164: body.contact_phone ?? v.contact_phone_e164 });
    return json(200, v);
  }
  if ((p = is("GET", "admin/vendors/:id/users")))
    return json(
      200,
      staff.filter((s) => s.vendor_id === p!.id),
    );
  if ((p = is("POST", "admin/vendors/:id/users")) || (p = is("POST", "admin/staff"))) {
    const isVendor = parts[1] === "vendors";
    const user: S["StaffUserOut"] = {
      id: id("user"),
      role: isVendor ? "VENDOR" : "ADMIN",
      email: String(body.email),
      full_name: String(body.full_name),
      vendor_id: isVendor ? p.id! : null,
      is_active: true,
      locked: false,
      last_login_at: null,
    };
    staff.push(user);
    return json(201, {
      user,
      temporary_password: "Temp-7g4K-29xQ",
      totp_provisioning_uri: isVendor
        ? null
        : "otpauth://totp/KitaabOnDemand:new?secret=JBSWY3DPEHPK3PXP",
    });
  }
  if ((p = is("GET", "admin/staff")))
    return json(
      200,
      staff.filter((s) => s.role === "ADMIN"),
    );
  if ((p = is("PATCH", "admin/staff/:id"))) {
    const user = staff.find((s) => s.id === p!.id)!;
    if (body.is_active != null) user.is_active = Boolean(body.is_active);
    if (body.unlock) user.locked = false;
    return json(200, user);
  }
  if ((p = is("GET", "admin/customers"))) {
    return json(
      200,
      page(
        [
          {
            id: "cust-1",
            full_name: "Ayesha Khan",
            phone_masked: "+92300*****67",
            order_count: orders.length,
            is_review_account: false,
            deleted: false,
            created_at: daysAgo(10),
          },
        ],
        url,
      ),
    );
  }
  if ((p = is("GET", "admin/customers/:id"))) {
    return json(200, {
      id: p.id,
      full_name: "Ayesha Khan",
      phone_e164: "+923001234567",
      email: null,
      google_linked: false,
      is_review_account: false,
      created_at: daysAgo(10),
      deleted_at: null,
      orders: orders.map(summary),
    });
  }

  // -- configuration
  if ((p = is("GET", "admin/pricing-configs"))) return json(200, [...pricingVersions].reverse());
  if ((p = is("POST", "admin/pricing-configs"))) {
    const version = pricingVersions.length + 1;
    pricingVersions.forEach((v) => (v.active = false));
    const created: S["PricingConfigVersion"] = {
      version,
      effective_from: String(body.effective_from),
      rules: body.rules as S["PricingRules"],
      notes: (body.notes as string | null) ?? null,
      created_by_name: signedIn.full_name,
      created_at: now(),
      active: true,
    };
    pricingVersions.push(created);
    return json(201, created);
  }
  if ((p = is("GET", "admin/cities"))) return json(200, cities);
  if ((p = is("POST", "admin/cities"))) {
    const c = { id: id("city"), ...(body as Omit<S["CityAdminOut"], "id">) };
    cities.push(c);
    return json(201, c);
  }
  if ((p = is("PUT", "admin/cities/:id"))) {
    const c = cities.find((x) => x.id === p!.id)!;
    Object.assign(c, body);
    return json(200, c);
  }
  if ((p = is("GET", "admin/settings"))) return json(200, settings);
  if ((p = is("PUT", "admin/settings"))) {
    settings = body as S["AppSettings"];
    return json(200, settings);
  }
  if ((p = is("GET", "admin/audit-logs"))) return json(200, page(auditLogs, url, 50));

  // -- finance
  if ((p = is("GET", "admin/finance/daily-revenue"))) {
    const rows: S["DailyRevenueRow"][] = [
      {
        date: daysAgo(1).slice(0, 10),
        payment_method: "COD",
        orders: 3,
        gross_paisa: 285000,
        refunds_paisa: 0,
        net_paisa: 285000,
      },
      {
        date: daysAgo(1).slice(0, 10),
        payment_method: "EASYPAISA",
        orders: 2,
        gross_paisa: 164000,
        refunds_paisa: 42000,
        net_paisa: 122000,
      },
      {
        date: daysAgo(0).slice(0, 10),
        payment_method: "CARD",
        orders: 1,
        gross_paisa: 99000,
        refunds_paisa: 0,
        net_paisa: 99000,
      },
    ];
    const sum = (k: "gross_paisa" | "refunds_paisa" | "net_paisa") =>
      rows.reduce((a, r) => a + r[k], 0);
    return json(200, {
      from_date: url.searchParams.get("from_date"),
      to_date: url.searchParams.get("to_date"),
      rows,
      total_gross_paisa: sum("gross_paisa"),
      total_refunds_paisa: sum("refunds_paisa"),
      total_net_paisa: sum("net_paisa"),
    });
  }
  if ((p = is("GET", "admin/finance/cod-pending"))) return json(200, codPending);
  if ((p = is("POST", "admin/finance/cod-remittances"))) {
    const group = codPending.find((g) => g.courier_code === body.courier_code)!;
    const ids = body.order_ids as string[];
    const remitted = group.orders.filter((o) => ids.includes(o.order_id));
    group.orders = group.orders.filter((o) => !ids.includes(o.order_id));
    group.total_paisa = group.orders.reduce((a, o) => a + o.amount_paisa, 0);
    return json(201, {
      courier_code: group.courier_code,
      orders: remitted.length,
      total_paisa: remitted.reduce((a, o) => a + o.amount_paisa, 0),
      reference: body.reference,
    });
  }
  if ((p = is("GET", "admin/finance/vendor-payouts"))) {
    return json(
      200,
      vendors.map((v, i) => ({
        vendor_id: v.id,
        vendor_name: v.name,
        accrued_paisa: 90000 * (i + 1),
        paid_paisa: 30000,
        in_open_batches_paisa: batches
          .filter((b) => b.vendor_id === v.id && b.status === "OPEN")
          .reduce((a, b) => a + b.total_paisa, 0),
        owed_paisa: 90000 * (i + 1) - 30000,
      })),
    );
  }
  if ((p = is("GET", "admin/finance/payout-batches"))) return json(200, batches);
  if ((p = is("POST", "admin/finance/payout-batches"))) {
    const vendor = vendors.find((v) => v.id === body.vendor_id)!;
    const batch: S["PayoutBatchOut"] = {
      id: id("batch"),
      vendor_id: vendor.id,
      vendor_name: vendor.name,
      status: "OPEN",
      total_paisa: 60000,
      reference: null,
      items: [{ order_id: "o-x1", order_code: "KD7ASSIGN", amount_paisa: 60000 }],
      created_at: now(),
      paid_at: null,
    };
    batches = [batch, ...batches];
    return json(201, batch);
  }
  if ((p = is("POST", "admin/finance/payout-batches/:id/mark-paid"))) {
    const batch = batches.find((b) => b.id === p!.id)!;
    Object.assign(batch, { status: "PAID", reference: body.reference, paid_at: now() });
    return json(200, batch);
  }
  if (method === "GET" && path.startsWith("/admin/finance/") && path.endsWith(".csv")) {
    return new Response("date,amount\n2026-10-09,1250\n", {
      headers: { "Content-Type": "text/csv" },
    });
  }
  throw new Problem(404, "not-found", `No mock for ${method} ${path}`);
}

// Snapshot of the seed data so tests can start from a clean state.
const initial = structuredClone({
  cities,
  vendors,
  staff,
  pricingVersions,
  settings,
  orders,
  auditLogs,
  refunds,
  codPending,
  batches,
});

/** Test helper: restore the seed data and sign out. */
export function resetMock() {
  const fresh = structuredClone(initial);
  cities.splice(0, cities.length, ...fresh.cities);
  vendors.splice(0, vendors.length, ...fresh.vendors);
  staff.splice(0, staff.length, ...fresh.staff);
  pricingVersions.splice(0, pricingVersions.length, ...fresh.pricingVersions);
  orders.splice(0, orders.length, ...fresh.orders);
  auditLogs.splice(0, auditLogs.length, ...fresh.auditLogs);
  codPending.splice(0, codPending.length, ...fresh.codPending);
  settings = fresh.settings;
  refunds = fresh.refunds;
  batches = fresh.batches;
  signedIn = null;
}

export async function mockFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const request = input instanceof Request ? input : new Request(input, init);
  const url = new URL(request.url);
  const text = request.method === "GET" || request.method === "HEAD" ? "" : await request.text();
  const body = text ? (JSON.parse(text) as Json) : {};
  await new Promise((resolve) => setTimeout(resolve, import.meta.env.MODE === "test" ? 0 : 150));
  try {
    return route(request.method, url, body);
  } catch (error) {
    if (error instanceof Problem) {
      return json(error.status, {
        type: `https://kitaabondemand.pk/problems/${error.code}`,
        title: error.title,
        status: error.status,
        code: error.code,
        ...(error.extra ? { extra: error.extra } : {}),
      });
    }
    throw error;
  }
}

/** Test helper: restore the signed-in user for component tests. */
export function mockSignIn(role: "ADMIN" | "VENDOR") {
  signedIn = role === "ADMIN" ? users["admin@example.com"]! : users["vendor@example.com"]!;
  return tokenPair(signedIn);
}
