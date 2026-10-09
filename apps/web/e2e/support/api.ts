import { createHmac } from "node:crypto";
import { expect, type APIRequestContext } from "@playwright/test";

/** Demo logins created by `kitaab seed --demo` (services/api/src/kitaab/cli.py). */
export const ADMIN = {
  email: "admin@example.com",
  password: "demo-admin-password",
  totpSecret: "JBSWY3DPEHPK3PXP",
};
export const VENDOR = { email: "vendor@example.com", password: "demo-vendor-password" };
export const DEMO_VENDOR_NAME = "Demo Print House";

function base32(secret: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let bits = "";
  for (const char of secret.replace(/=+$/, "")) {
    bits += alphabet.indexOf(char).toString(2).padStart(5, "0");
  }
  const bytes = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) bytes.push(parseInt(bits.slice(i, i + 8), 2));
  return Buffer.from(bytes);
}

/** RFC 6238 code (SHA-1, 30 seconds, 6 digits), as an authenticator app shows. */
export function totpCode(secret: string, at = Date.now()): string {
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(at / 1000 / 30)));
  const digest = createHmac("sha1", base32(secret)).update(counter).digest();
  const offset = digest[digest.length - 1] & 0x0f;
  const value = (digest.readUInt32BE(offset) & 0x7fffffff) % 1_000_000;
  return value.toString().padStart(6, "0");
}

/** A small valid PDF with the given number of pages. */
export function pdfBytes(pages: number): Buffer {
  const objects: string[] = [];
  const kids = Array.from({ length: pages }, (_, i) => `${3 + i} 0 R`).join(" ");
  objects.push("<< /Type /Catalog /Pages 2 0 R >>");
  objects.push(`<< /Type /Pages /Kids [${kids}] /Count ${pages} >>`);
  for (let i = 0; i < pages; i++) {
    objects.push("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] >>");
  }
  let body = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((object, i) => {
    offsets.push(Buffer.byteLength(body));
    body += `${i + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xref = Buffer.byteLength(body);
  body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  body += offsets.map((o) => `${String(o).padStart(10, "0")} 00000 n \n`).join("");
  body += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(body, "latin1");
}

export interface Customer {
  phone: string;
  headers: Record<string, string>;
  addressId: string;
}

async function ok<T>(response: Awaited<ReturnType<APIRequestContext["get"]>>): Promise<T> {
  expect(response.ok(), `${response.url()} → ${response.status()} ${await response.text()}`).toBe(
    true,
  );
  return (await response.json()) as T;
}

/** Signs a customer in by OTP (code from the development SMS outbox). */
export async function signUpCustomer(request: APIRequestContext): Promise<Customer> {
  const phone = `0300${String(Math.floor(Math.random() * 10_000_000)).padStart(7, "0")}`;
  const sent = await ok<{ phone_e164: string }>(
    await request.post("/api/v1/auth/otp/request", { data: { phone } }),
  );
  const outbox = await ok<{ to: string; text: string }[]>(
    await request.get("/api/v1/_dev/sms-outbox", { params: { phone: sent.phone_e164 } }),
  );
  const code = outbox[0].text.match(/\b\d{6}\b/)![0];
  const pair = await ok<{ access_token: string }>(
    await request.post("/api/v1/auth/otp/verify", { data: { phone, code } }),
  );
  const headers = { Authorization: `Bearer ${pair.access_token}` };
  const config = await ok<{ terms_version: string }>(await request.get("/api/v1/app/config"));
  await ok(
    await request.post("/api/v1/me/terms", {
      headers,
      data: { terms_version: config.terms_version },
    }),
  );
  await ok(await request.patch("/api/v1/me", { headers, data: { full_name: "Sana Tariq" } }));
  const cities = await ok<{ id: string; name: string }[]>(await request.get("/api/v1/cities"));
  const lahore = cities.find((c) => c.name === "Lahore")!;
  const address = await ok<{ id: string }>(
    await request.post("/api/v1/me/addresses", {
      headers,
      data: {
        recipient_name: "Sana Tariq",
        recipient_phone: phone,
        city_id: lahore.id,
        area: "Model Town",
        street_address: "House 5, Block K",
        landmark: "Near Model Town Park",
        is_default: true,
      },
    }),
  );
  return { phone, headers, addressId: address.id };
}

/** Uploads a PDF through the presigned URLs and waits for the worker to validate it. */
export async function uploadPdf(
  request: APIRequestContext,
  customer: Customer,
  pages: number,
): Promise<string> {
  const content = pdfBytes(pages);
  const session = await ok<{ upload: { id: string }; parts: { url: string }[] }>(
    await request.post("/api/v1/uploads", {
      headers: customer.headers,
      data: { filename: "lecture-notes.pdf", size_bytes: content.length, copyright_declared: true },
    }),
  );
  const put = await request.put(session.parts[0].url, { data: content });
  expect(put.ok(), `storage upload → ${put.status()}`).toBe(true);
  const id = session.upload.id;
  await ok(await request.post(`/api/v1/uploads/${id}/complete`, { headers: customer.headers }));
  await expect
    .poll(
      async () =>
        (
          await ok<{ status: string }>(
            await request.get(`/api/v1/uploads/${id}`, { headers: customer.headers }),
          )
        ).status,
      { timeout: 30_000 },
    )
    .toBe("VALID");
  return id;
}

export interface CreatedOrder {
  id: string;
  code: string;
  total_paisa: number;
}

export async function placePrintOrder(
  request: APIRequestContext,
  customer: Customer,
  pages = 24,
): Promise<CreatedOrder> {
  const uploadId = await uploadPdf(request, customer, pages);
  const cities = await ok<{ id: string; name: string }[]>(await request.get("/api/v1/cities"));
  const options = {
    paper: "LOCAL_WHITE",
    binding: "SOFTCOVER_PAPERBACK",
    copies: 1,
  };
  const price = await ok<{ total_paisa: number }>(
    await request.post("/api/v1/pricing/quote", {
      data: {
        ...options,
        pages,
        city_id: cities.find((c) => c.name === "Lahore")!.id,
        payment_method: "COD",
      },
    }),
  );
  return ok<CreatedOrder>(
    await request.post("/api/v1/orders/print", {
      headers: customer.headers,
      data: {
        ...options,
        upload_id: uploadId,
        address_id: customer.addressId,
        payment_method: "COD",
        expected_total_paisa: price.total_paisa,
      },
    }),
  );
}

export async function requestBook(
  request: APIRequestContext,
  customer: Customer,
  title: string,
): Promise<CreatedOrder> {
  return ok<CreatedOrder>(
    await request.post("/api/v1/orders/source", {
      headers: customer.headers,
      data: {
        book_title: title,
        author: "Mustansar Hussain Tarar",
        copies: 1,
        address_id: customer.addressId,
      },
    }),
  );
}

/** Moves a mock parcel; the mock courier then posts a signed webhook to the API. */
export async function courierEvent(request: APIRequestContext, cn: string, state: string) {
  await ok(await request.post(`/api/v1/_dev/mock-courier/${cn}/events`, { data: { state } }));
}
