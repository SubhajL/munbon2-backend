import { NextRequest } from "next/server";
import { describe, expect, test } from "vitest";
import { POST } from "./route";

describe("POST /api/auth/login", () => {
  test.each([{ email: "a@b.c" }, { password: "pw" }, {}])(
    "rejects a credential-less body (%j) with 400 before any upstream call",
    async (body) => {
      const req = new NextRequest("http://localhost/api/auth/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });

      const res = await POST(req);
      expect(res.status).toBe(400);
      expect(await res.json()).toEqual({
        error: "Email and password are required",
      });
    },
  );
});
