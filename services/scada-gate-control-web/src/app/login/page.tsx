"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { LoginForm } from "@/components/LoginForm";
import { AuthError } from "@/lib/auth-client";
import { isSafeNext } from "@/lib/redirect";

export function LoginScreen() {
  const router = useRouter();
  const params = useSearchParams();
  const { login, status } = useAuth();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nextParam = params.get("next");
  const next = nextParam && isSafeNext(nextParam) ? nextParam : "/";

  // Already signed in (e.g. opened /login directly) — bounce to the target.
  useEffect(() => {
    if (status === "authenticated") router.replace(next);
  }, [status, next, router]);

  async function handleSubmit(email: string, password: string) {
    setPending(true);
    setError(null);
    try {
      await login(email, password);
      router.replace(next);
    } catch (err) {
      setError(
        err instanceof AuthError
          ? err.message
          : "Sign-in failed. Please try again.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center p-6">
      <div className="w-full max-w-sm rounded-2xl border border-border bg-surface p-6 shadow-lg">
        <header className="mb-6 space-y-1">
          <h1 className="text-lg font-semibold text-fg">
            มูลบน เฟส 2 (Munbon Phase 2)
          </h1>
          <p className="text-xs text-fg-muted">
            เข้าสู่ระบบควบคุมประตูน้ำ (Gate control sign-in)
          </p>
        </header>
        <LoginForm onSubmit={handleSubmit} pending={pending} error={error} />
      </div>
    </main>
  );
}

export default function LoginPage() {
  // useSearchParams requires a Suspense boundary during static generation.
  return (
    <Suspense>
      <LoginScreen />
    </Suspense>
  );
}
