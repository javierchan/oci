"use client";

import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

import { APP_ICON_PATH, APP_NAME, APP_TAGLINE } from "@/lib/app-brand";
import { api, getErrorMessage } from "@/lib/api";


function safeNextPath(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/projects";
}


function LoginForm(): JSX.Element {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await api.login({ username: username.trim(), password });
      router.replace(safeNextPath(searchParams.get("next")));
      router.refresh();
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to sign in."));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[var(--color-page-bg)] px-4 py-10">
      <section className="w-full max-w-md rounded-2xl border border-[var(--color-border)] bg-[var(--color-surface)] p-7 shadow-[var(--shadow-3)] sm:p-9">
        <div className="flex items-center gap-4 border-b border-[var(--color-border)] pb-6">
          <Image src={APP_ICON_PATH} alt="" width={56} height={56} className="h-14 w-14 rounded-2xl" />
          <div>
            <h1 className="text-2xl font-semibold text-[var(--color-text-primary)]">{APP_NAME}</h1>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">{APP_TAGLINE}</p>
          </div>
        </div>

        <div className="py-6">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--color-text-muted)]">Local authentication</p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Sign in to your workspace</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            Your account determines which projects and governed records you can access.
          </p>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="block text-sm font-medium text-[var(--color-text-primary)]">
            Username
            <input
              autoComplete="username"
              autoFocus
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5 text-[var(--color-text-primary)] outline-none focus:border-[var(--accent)]"
            />
          </label>
          <label className="block text-sm font-medium text-[var(--color-text-primary)]">
            Password
            <input
              autoComplete="current-password"
              required
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5 text-[var(--color-text-primary)] outline-none focus:border-[var(--accent)]"
            />
          </label>
          {error ? (
            <p role="alert" className="rounded-lg border border-[var(--err)]/25 bg-[var(--err-bg)] px-3 py-2 text-sm text-[var(--err)]">
              {error}
            </p>
          ) : null}
          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-[var(--accent)] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="mt-6 text-xs leading-5 text-[var(--color-text-muted)]">
          OCI IAM will be available later as an additional sign-in method for the same App identity.
        </p>
      </section>
    </main>
  );
}


export default function LoginPage(): JSX.Element {
  return (
    <Suspense fallback={<main className="min-h-screen bg-[var(--color-page-bg)]" />}>
      <LoginForm />
    </Suspense>
  );
}
