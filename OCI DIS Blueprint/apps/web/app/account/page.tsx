"use client";

import { FormEvent, useEffect, useState } from "react";
import { Check, Copy, KeyRound, ShieldCheck, Trash2 } from "lucide-react";

import { api, getErrorMessage } from "@/lib/api";
import type { ApiTokenRecord, ApiTokenScope, AuthUser, Project } from "@/lib/types";


export default function AccountPage(): JSX.Element {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [tokens, setTokens] = useState<ApiTokenRecord[]>([]);
  const [scopeCatalog, setScopeCatalog] = useState<ApiTokenScope[]>([]);
  const [tokenName, setTokenName] = useState("");
  const [expiresInDays, setExpiresInDays] = useState(90);
  const [selectedProjects, setSelectedProjects] = useState<string[]>([]);
  const [selectedScopes, setSelectedScopes] = useState<string[]>(["projects:read"]);
  const [createdToken, setCreatedToken] = useState("");
  const [createdTokenId, setCreatedTokenId] = useState("");
  const [copied, setCopied] = useState(false);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  useEffect(() => {
    let active = true;
    void Promise.all([api.getCurrentUser(), api.listProjects(), api.listApiTokens(), api.listApiTokenScopes()])
      .then(([session, projectList, tokenList, scopes]) => {
        if (!active) return;
        setUser(session.user);
        setProjects(projectList.projects);
        setTokens(tokenList.tokens);
        setScopeCatalog(scopes.scopes);
      })
      .catch((error) => {
        if (active) setMessage(getErrorMessage(error, "Unable to load account settings."));
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleCreateToken(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const created = await api.createApiToken({
        name: tokenName,
        expires_in_days: expiresInDays,
        project_ids: selectedProjects.length > 0 ? selectedProjects : null,
        scopes: selectedScopes,
      });
      setCreatedToken(created.token);
      setCreatedTokenId(created.id);
      setTokens((current) => [created, ...current]);
      setTokenName("");
      setSelectedProjects([]);
      setCopied(false);
    } catch (error) {
      setMessage(getErrorMessage(error, "Unable to create API token."));
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke(tokenId: string): Promise<void> {
    setBusy(true);
    setMessage("");
    try {
      await api.revokeApiToken(tokenId);
      if (tokenId === createdTokenId) {
        setCreatedToken("");
        setCreatedTokenId("");
        setCopied(false);
      }
      setTokens((current) => current.map((token) => (
        token.id === tokenId ? { ...token, revoked_at: new Date().toISOString() } : token
      )));
    } catch (error) {
      setMessage(getErrorMessage(error, "Unable to revoke API token."));
    } finally {
      setBusy(false);
    }
  }

  async function handleChangePassword(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      await api.changePassword({ current_password: currentPassword, new_password: newPassword });
      setCurrentPassword("");
      setNewPassword("");
      setMessage("Password updated. Other browser sessions were revoked.");
    } catch (error) {
      setMessage(getErrorMessage(error, "Unable to change password."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header>
        <p className="console-eyebrow">Identity & access</p>
        <h1 className="mt-2 text-3xl font-semibold text-[var(--color-text-primary)]">Account security</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
          Local sessions, future OCI IAM identities, and external API tokens share one user and the same project memberships.
        </p>
      </header>

      {message ? <p role="status" className="console-panel px-4 py-3 text-sm">{message}</p> : null}

      <section className="console-panel p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="console-eyebrow">Authenticated user</p>
            <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">{user?.display_name ?? "Loading…"}</h2>
            <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{user?.username ? `@${user.username} · ` : ""}{user?.email}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="console-pill">{user?.role ?? "Role"}</span>
            <span className="console-pill">{user?.project_count ?? 0} projects</span>
            <span className="console-pill">Local</span>
            <span className="console-pill opacity-70">OCI IAM · future</span>
          </div>
        </div>
      </section>

      <section className="console-panel p-5">
        <div className="flex items-start gap-3">
          <KeyRound className="mt-1 h-5 w-5 text-[var(--accent)]" />
          <div>
            <h2 className="text-xl font-semibold text-[var(--color-text-primary)]">External API tokens</h2>
            <p className="mt-1 text-sm leading-6 text-[var(--color-text-secondary)]">
              Tokens are read-only, inherit your current project memberships, and can be narrowed to selected projects. Use <code>Authorization: Bearer &lt;token&gt;</code>.
            </p>
          </div>
        </div>

        <form onSubmit={handleCreateToken} className="mt-5 grid gap-4 border-t border-[var(--color-border)] pt-5 md:grid-cols-2">
          <label className="text-sm font-medium text-[var(--color-text-primary)]">
            Token name
            <input required value={tokenName} onChange={(event) => setTokenName(event.target.value)} placeholder="Codex read access" className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5" />
          </label>
          <label className="text-sm font-medium text-[var(--color-text-primary)]">
            Expires in days
            <input required min={1} max={365} type="number" value={expiresInDays} onChange={(event) => setExpiresInDays(Number(event.target.value))} className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5" />
          </label>
          <fieldset className="md:col-span-2">
            <legend className="text-sm font-medium text-[var(--color-text-primary)]">Project scope</legend>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">Leave all unchecked to follow every current membership. Select projects to narrow the token.</p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {projects.map((project) => (
                <label key={project.id} className="flex items-center gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedProjects.includes(project.id)}
                    onChange={(event) => setSelectedProjects((current) => event.target.checked ? [...current, project.id] : current.filter((id) => id !== project.id))}
                  />
                  <span className="truncate">{project.name}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className="md:col-span-2">
            <legend className="text-sm font-medium text-[var(--color-text-primary)]">API permissions</legend>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">Choose only the read capabilities this client needs. Tokens can never mutate App data.</p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {scopeCatalog.map((scope) => (
                <label key={scope.code} className="flex items-start gap-2 rounded-lg border border-[var(--color-border)] px-3 py-2 text-sm">
                  <input
                    className="mt-1"
                    type="checkbox"
                    checked={selectedScopes.includes(scope.code)}
                    onChange={(event) => setSelectedScopes((current) => event.target.checked ? [...current, scope.code] : current.filter((code) => code !== scope.code))}
                  />
                  <span><span className="block font-medium">{scope.label}</span><span className="mt-0.5 block text-xs leading-5 text-[var(--color-text-muted)]">{scope.description}</span></span>
                </label>
              ))}
            </div>
          </fieldset>
          <div className="md:col-span-2">
            <button disabled={busy || selectedScopes.length === 0} type="submit" className="rounded-lg bg-[var(--accent)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60">Create read-only token</button>
          </div>
        </form>

        {createdToken ? (
          <div className="mt-5 rounded-xl border border-[var(--warn)]/40 bg-[var(--warn-bg)] p-4">
            <p className="font-semibold text-[var(--color-text-primary)]">Copy this token now</p>
            <p className="mt-1 text-xs text-[var(--color-text-secondary)]">It will not be shown again.</p>
            <div className="mt-3 flex gap-2">
              <code className="min-w-0 flex-1 overflow-x-auto rounded-lg bg-[var(--color-surface)] px-3 py-2 text-xs">{createdToken}</code>
              <button type="button" onClick={() => void navigator.clipboard.writeText(createdToken).then(() => setCopied(true))} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3" aria-label="Copy API token">
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </button>
            </div>
          </div>
        ) : null}

        <div className="mt-5 space-y-2">
          {tokens.map((token) => (
            <div key={token.id} className="flex flex-wrap items-center gap-3 rounded-lg border border-[var(--color-border)] px-3 py-3">
              <div className="min-w-0 flex-1">
                <p className="font-medium text-[var(--color-text-primary)]">{token.name}</p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">{token.token_prefix}… · {token.project_ids?.length ? `${token.project_ids.length} selected projects` : "all memberships"} · {token.scopes.includes("api:read") ? "legacy full read" : `${token.scopes.length} permissions`} · expires {token.expires_at ? new Date(token.expires_at).toLocaleDateString() : "never"}</p>
              </div>
              <span className="console-pill">{token.revoked_at ? "Revoked" : "Read only"}</span>
              {!token.revoked_at ? <button disabled={busy} type="button" onClick={() => void handleRevoke(token.id)} className="rounded-lg p-2 text-[var(--color-text-muted)] hover:bg-[var(--err-bg)] hover:text-[var(--err)]" aria-label={`Revoke ${token.name}`}><Trash2 className="h-4 w-4" /></button> : null}
            </div>
          ))}
        </div>
      </section>

      <section className="console-panel p-5">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-1 h-5 w-5 text-[var(--accent)]" />
          <div>
            <h2 className="text-xl font-semibold text-[var(--color-text-primary)]">Local password</h2>
            <p className="mt-1 text-sm text-[var(--color-text-secondary)]">Changing it revokes every other browser session.</p>
          </div>
        </div>
        <form onSubmit={handleChangePassword} className="mt-5 grid gap-4 border-t border-[var(--color-border)] pt-5 md:grid-cols-2">
          <label className="text-sm font-medium">Current password<input required type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5" /></label>
          <label className="text-sm font-medium">New password<input required minLength={12} type="password" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5" /></label>
          <button disabled={busy} type="submit" className="w-fit rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-4 py-2.5 text-sm font-semibold disabled:opacity-60">Update password</button>
        </form>
      </section>
    </div>
  );
}
