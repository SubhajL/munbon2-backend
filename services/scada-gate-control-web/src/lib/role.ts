/**
 * Client-side role derivation, used ONLY to disable controls the user can't
 * use (the backend is the real authority and re-checks every command). Mirrors
 * the backend DEFAULT_ROLE_MAPPING.
 */
export type AppRole = "viewer" | "operator" | "admin";

const ADMIN_ROLE_NAMES = ["super_admin", "rid_admin"];
const OPERATOR_ROLE_NAMES = ["zone_manager"];

export function mapAppRole(roleNames: readonly string[]): AppRole {
  if (roleNames.some((name) => ADMIN_ROLE_NAMES.includes(name))) return "admin";
  if (roleNames.some((name) => OPERATOR_ROLE_NAMES.includes(name)))
    return "operator";
  return "viewer";
}

export function canCommand(role: AppRole): boolean {
  return role === "operator" || role === "admin";
}

function decodeJwtPayload(token: string): unknown {
  const segment = token.split(".")[1];
  if (!segment) return null;
  const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64.padEnd(
    base64.length + ((4 - (base64.length % 4)) % 4),
    "=",
  );
  const json =
    typeof atob !== "undefined"
      ? atob(padded)
      : Buffer.from(padded, "base64").toString("utf8");
  return JSON.parse(json);
}

export type TokenUser = { email: string | null; role: AppRole };

/**
 * Best-effort identity from an access JWT (`email` + mapped `roles` claims);
 * falls back to an anonymous viewer when the token is missing or malformed.
 */
export function userFromToken(token: string | undefined): TokenUser {
  if (!token) return { email: null, role: "viewer" };
  try {
    const payload = decodeJwtPayload(token) as {
      roles?: unknown;
      email?: unknown;
    } | null;
    const roles = Array.isArray(payload?.roles)
      ? payload.roles.filter((r): r is string => typeof r === "string")
      : [];
    const email = typeof payload?.email === "string" ? payload.email : null;
    return { email, role: mapAppRole(roles) };
  } catch {
    return { email: null, role: "viewer" };
  }
}
