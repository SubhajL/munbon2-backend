/**
 * Shared glue between the auth BFF route handlers and the pure `auth-proxy`
 * logic: reads the incoming refresh cookie and turns a `ProxyResponse` into a
 * `NextResponse`, re-issuing the refresh token as a SAME-ORIGIN, httpOnly cookie
 * scoped to `/api/auth` (so only the refresh/logout handlers ever receive it).
 */
import { NextResponse, type NextRequest } from "next/server";
import { REFRESH_COOKIE, type ProxyResponse } from "./auth-proxy";

const COOKIE_OPTS = {
  httpOnly: true,
  sameSite: "lax" as const,
  secure: process.env.NODE_ENV === "production",
  path: "/api/auth",
  maxAge: 60 * 60 * 24 * 7, // 7 days, matching the upstream refresh-token lifetime
};

export function readRefreshCookie(req: NextRequest): string | undefined {
  return req.cookies.get(REFRESH_COOKIE)?.value;
}

export function toNextResponse(result: ProxyResponse): NextResponse {
  const res = NextResponse.json(result.body, { status: result.status });
  if (result.setRefreshCookie) {
    res.cookies.set(REFRESH_COOKIE, result.setRefreshCookie, COOKIE_OPTS);
  }
  if (result.clearRefreshCookie) {
    res.cookies.set(REFRESH_COOKIE, "", { ...COOKIE_OPTS, maxAge: 0 });
  }
  return res;
}
