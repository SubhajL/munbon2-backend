"use client";

/**
 * Route guard for protected screens: redirects to `/login?next=…` when the user
 * is unauthenticated, shows nothing while the session is still resolving, and
 * otherwise renders the page with a persistent account badge (identity + role +
 * log out) pinned to the top-right.
 */
import { useEffect, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "./AuthProvider";
import type { SessionUser } from "@/lib/auth-client";

function AccountBadge({
  user,
  onLogout,
}: {
  user: SessionUser;
  onLogout: () => void;
}) {
  return (
    <div className="pointer-events-none fixed right-4 top-4 z-50">
      <div className="pointer-events-auto flex items-center gap-3 rounded-lg border border-border bg-surface/90 px-3 py-2 text-xs shadow-lg backdrop-blur">
        <span className="text-fg">{user.email ?? "signed in"}</span>
        <span className="rounded-full bg-surface-low px-2 py-0.5 text-[10px] uppercase tracking-wide text-fg-muted">
          {user.role}
        </span>
        <button
          type="button"
          onClick={onLogout}
          className="rounded-md border border-border px-2 py-1 text-fg-muted hover:text-fg"
        >
          ออกจากระบบ (Log out)
        </button>
      </div>
    </div>
  );
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status, session, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (status === "unauthenticated") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [status, pathname, router]);

  if (status !== "authenticated" || !session) {
    return (
      <div
        className="flex h-dvh items-center justify-center text-sm text-fg-muted"
        role="status"
      >
        กำลังตรวจสอบสิทธิ์… (checking access)
      </div>
    );
  }

  return (
    <>
      <AccountBadge user={session.user} onLogout={logout} />
      {children}
    </>
  );
}
