/**
 * Validates a post-login `?next=` redirect target. Accepts ONLY same-origin
 * absolute paths and rejects anything that could navigate off-origin:
 * protocol-relative (`//`, `/\`) and their percent-encoded forms, absolute URLs,
 * and scheme-bearing strings. The path is resolved against a dummy origin and
 * must round-trip back to that origin.
 */
export function isSafeNext(next: string): boolean {
  if (!next.startsWith("/")) return false;
  // Reject protocol-relative / backslash escapes, including encoded variants.
  if (/^\/[/\\]/.test(next) || /^\/%2f/i.test(next) || /^\/%5c/i.test(next)) {
    return false;
  }
  try {
    const base = "http://localhost";
    return new URL(next, base).origin === base;
  } catch {
    return false;
  }
}
