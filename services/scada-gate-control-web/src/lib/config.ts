/**
 * Public (browser-visible) client config. Server-only config (the upstream auth
 * service URL, cookie name) lives in `auth-proxy.ts` so it is never bundled into
 * client code.
 */
export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:3030";

/**
 * Dev-only escape hatch: when set, the app skips the login flow and uses this
 * token as the Bearer for SCADA calls. Never set in production.
 */
export const DEV_TOKEN = process.env.NEXT_PUBLIC_DEV_TOKEN || undefined;
