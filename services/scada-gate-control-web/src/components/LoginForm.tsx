"use client";

/**
 * Presentational sign-in form. All wiring (auth call, redirect, error capture)
 * lives in the page that owns it; this component only collects credentials and
 * reflects the pending/error state it is given.
 */
import { useState, type FormEvent } from "react";

export type LoginFormProps = {
  onSubmit: (email: string, password: string) => void | Promise<void>;
  pending?: boolean;
  error?: string | null;
};

export function LoginForm({
  onSubmit,
  pending = false,
  error = null,
}: LoginFormProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onSubmit(email, password);
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex w-full flex-col gap-4"
      aria-label="Sign in"
    >
      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="login-email"
          className="text-xs font-medium text-fg-muted"
        >
          อีเมล (Email)
        </label>
        <input
          id="login-email"
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="rounded-md border border-border bg-surface-low px-3 py-2 text-sm text-fg outline-none focus:border-primary"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <label
          htmlFor="login-password"
          className="text-xs font-medium text-fg-muted"
        >
          รหัสผ่าน (Password)
        </label>
        <input
          id="login-password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="rounded-md border border-border bg-surface-low px-3 py-2 text-sm text-fg outline-none focus:border-primary"
        />
      </div>

      {error ? (
        <p role="alert" className="text-xs text-[var(--color-offline)]">
          {error}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={pending}
        className="mt-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-fg disabled:opacity-60"
      >
        {pending ? "กำลังเข้าสู่ระบบ… (Signing in…)" : "เข้าสู่ระบบ (Sign in)"}
      </button>
    </form>
  );
}
