"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { KeyRound, Plus, ShieldCheck, UserRoundCheck, UsersRound } from "lucide-react";

import { api, getErrorMessage } from "@/lib/api";
import type { AppRole, ManagedUser, Project } from "@/lib/types";


const APP_ROLES: Array<{ value: AppRole; label: string; detail: string }> = [
  { value: "Admin", label: "Admin", detail: "User, governance, pricing, and full project authority." },
  { value: "Architect", label: "Architect", detail: "Architecture decisions, approvals, and governed design changes." },
  { value: "Analyst", label: "Analyst", detail: "Import, review, analysis, and non-approval project work." },
  { value: "Viewer", label: "Viewer", detail: "Read-only access to assigned projects." },
];

type UserForm = {
  username: string;
  email: string;
  displayName: string;
  role: AppRole;
  isActive: boolean;
  password: string;
  memberships: Record<string, "Contributor" | "Viewer">;
};

function emptyForm(): UserForm {
  return {
    username: "",
    email: "",
    displayName: "",
    role: "Viewer",
    isActive: true,
    password: "",
    memberships: {},
  };
}

function formFromUser(user: ManagedUser): UserForm {
  return {
    username: user.username ?? "",
    email: user.email,
    displayName: user.display_name,
    role: user.role,
    isActive: user.is_active,
    password: "",
    memberships: Object.fromEntries(
      user.memberships
        .filter((membership) => membership.project_role !== "Owner")
        .map((membership) => [
          membership.project_id,
          membership.project_role as "Contributor" | "Viewer",
        ]),
    ),
  };
}


export default function UserManagementPage(): JSX.Element {
  const [users, setUsers] = useState<ManagedUser[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<UserForm>(emptyForm);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedId) ?? null,
    [selectedId, users],
  );

  async function refresh(preferredUserId?: string): Promise<void> {
    const [managed, projectList] = await Promise.all([api.listManagedUsers(), api.listProjects()]);
    setUsers(managed.users);
    setProjects(projectList.projects);
    const next = managed.users.find((user) => user.id === preferredUserId)
      ?? managed.users.find((user) => user.id === selectedId)
      ?? managed.users[0]
      ?? null;
    if (!creating && next) {
      setSelectedId(next.id);
      setForm(formFromUser(next));
    }
  }

  useEffect(() => {
    let active = true;
    void Promise.all([api.listManagedUsers(), api.listProjects()])
      .then(([managed, projectList]) => {
        if (!active) return;
        setUsers(managed.users);
        setProjects(projectList.projects);
        const first = managed.users[0] ?? null;
        if (first) {
          setSelectedId(first.id);
          setForm(formFromUser(first));
        }
      })
      .catch((caught) => {
        if (active) setError(getErrorMessage(caught, "Unable to load user management."));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function selectUser(user: ManagedUser): void {
    setCreating(false);
    setSelectedId(user.id);
    setForm(formFromUser(user));
    setError("");
    setMessage("");
  }

  function startCreate(): void {
    setCreating(true);
    setSelectedId(null);
    setForm(emptyForm());
    setError("");
    setMessage("");
  }

  function toggleProject(projectId: string, checked: boolean): void {
    setForm((current) => {
      const memberships = { ...current.memberships };
      if (checked) memberships[projectId] = "Contributor";
      else delete memberships[projectId];
      return { ...current, memberships };
    });
  }

  async function save(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    const memberships = Object.entries(form.memberships).map(([project_id, project_role]) => ({
      project_id,
      project_role,
    }));
    try {
      let saved: ManagedUser;
      if (creating) {
        saved = await api.createManagedUser({
          username: form.username,
          email: form.email,
          display_name: form.displayName,
          role: form.role,
          password: form.password,
          memberships,
        });
      } else {
        if (!selectedUser) throw new Error("Select a user first.");
        saved = await api.updateManagedUser(selectedUser.id, {
          username: form.username,
          email: form.email,
          display_name: form.displayName,
          role: form.role,
          is_active: form.isActive,
          ...(form.password ? { reset_password: form.password } : {}),
        });
        saved = await api.replaceManagedUserMemberships(saved.id, memberships);
      }
      setCreating(false);
      setSelectedId(saved.id);
      setForm(formFromUser(saved));
      await refresh(saved.id);
      setMessage(creating ? "User created and project access assigned." : "User identity, role, and project access updated.");
    } catch (caught) {
      setError(getErrorMessage(caught, "Unable to save this user."));
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <p className="text-sm text-[var(--color-text-secondary)]">Loading user management…</p>;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="console-eyebrow">Identity & access</p>
          <h1 className="mt-2 text-3xl font-semibold">User management</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
            Create local users, edit their username without breaking identity history, assign App roles, and control project membership.
          </p>
        </div>
        <button type="button" onClick={startCreate} className="app-button-primary gap-2"><Plus className="h-4 w-4" /> New user</button>
      </header>

      {error ? <p role="alert" className="rounded-xl border border-[var(--err)]/30 bg-[var(--err-bg)] px-4 py-3 text-sm text-[var(--err)]">{error}</p> : null}
      {message ? <p role="status" className="rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-200">{message}</p> : null}

      <div className="grid gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <section className="console-panel min-h-[36rem] overflow-hidden">
          <div className="border-b border-[var(--color-border)] px-4 py-4">
            <div className="flex items-center gap-2"><UsersRound className="h-5 w-5 text-[var(--accent)]" /><h2 className="font-semibold">Users</h2></div>
            <p className="mt-1 text-xs text-[var(--color-text-muted)]">{users.length} governed identities</p>
          </div>
          <div className="divide-y divide-[var(--color-border)]">
            {users.map((user) => (
              <button key={user.id} type="button" onClick={() => selectUser(user)} className={`w-full px-4 py-4 text-left transition hover:bg-[var(--color-hover)] ${selectedId === user.id && !creating ? "bg-[var(--color-surface-2)]" : ""}`}>
                <span className="flex items-start justify-between gap-3">
                  <span className="min-w-0"><span className="block truncate font-semibold">{user.display_name}</span><span className="mt-1 block truncate font-mono text-xs text-[var(--color-text-muted)]">@{user.username ?? "no-local-username"}</span></span>
                  <span className="console-pill">{user.role}</span>
                </span>
                <span className="mt-2 block text-xs text-[var(--color-text-muted)]">{user.memberships.length} projects · {user.is_active ? "Active" : "Disabled"}</span>
              </button>
            ))}
          </div>
        </section>

        <form onSubmit={save} className="console-panel p-5">
          <div className="flex items-start gap-3 border-b border-[var(--color-border)] pb-5">
            {creating ? <UserRoundCheck className="mt-1 h-5 w-5 text-[var(--accent)]" /> : <ShieldCheck className="mt-1 h-5 w-5 text-[var(--accent)]" />}
            <div><p className="console-eyebrow">{creating ? "New local identity" : "Governed identity"}</p><h2 className="mt-1 text-xl font-semibold">{creating ? "Create user" : selectedUser?.display_name ?? "Select a user"}</h2></div>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <label className="text-sm font-medium">Username<input required value={form.username} onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))} className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5" /><span className="mt-1 block text-xs font-normal text-[var(--color-text-muted)]">Editable; sessions and history remain linked to the same App user.</span></label>
            <label className="text-sm font-medium">Email<input required type="email" value={form.email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5" /></label>
            <label className="text-sm font-medium">Display name<input required value={form.displayName} onChange={(event) => setForm((current) => ({ ...current, displayName: event.target.value }))} className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5" /></label>
            <label className="text-sm font-medium">App role<select value={form.role} onChange={(event) => setForm((current) => ({ ...current, role: event.target.value as AppRole }))} className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5">{APP_ROLES.map((role) => <option key={role.value} value={role.value}>{role.label}</option>)}</select><span className="mt-1 block text-xs font-normal text-[var(--color-text-muted)]">{APP_ROLES.find((role) => role.value === form.role)?.detail}</span></label>
            <label className="text-sm font-medium md:col-span-2"><span className="inline-flex items-center gap-2"><KeyRound className="h-4 w-4" />{creating ? "Initial password" : "Reset password (optional)"}</span><input required={creating} minLength={12} type="password" autoComplete="new-password" value={form.password} onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))} className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-2.5" /><span className="mt-1 block text-xs font-normal text-[var(--color-text-muted)]">An admin reset revokes that user&apos;s sessions and API tokens.</span></label>
            {!creating ? <label className="flex items-center gap-2 text-sm font-medium md:col-span-2"><input type="checkbox" checked={form.isActive} onChange={(event) => setForm((current) => ({ ...current, isActive: event.target.checked }))} /> Active account</label> : null}
          </div>

          <fieldset className="mt-6 border-t border-[var(--color-border)] pt-5">
            <legend className="font-semibold">Project access</legend>
            <p className="mt-1 text-xs leading-5 text-[var(--color-text-muted)]">App role controls allowed actions. Membership controls which project data the user can reach. Owned projects cannot be removed here.</p>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              {projects.map((project) => {
                const owner = selectedUser?.memberships.some((membership) => membership.project_id === project.id && membership.project_role === "Owner") ?? false;
                const assigned = owner || project.id in form.memberships;
                return (
                  <div key={project.id} className="rounded-lg border border-[var(--color-border)] p-3">
                    <label className="flex items-start gap-2 text-sm"><input className="mt-1" type="checkbox" disabled={owner} checked={assigned} onChange={(event) => toggleProject(project.id, event.target.checked)} /><span className="min-w-0 flex-1"><span className="block truncate font-medium">{project.name}</span><span className="mt-1 block text-xs text-[var(--color-text-muted)]">{owner ? "Owner · required" : project.customer_name}</span></span></label>
                    {assigned && !owner ? <select aria-label={`${project.name} membership role`} value={form.memberships[project.id]} onChange={(event) => setForm((current) => ({ ...current, memberships: { ...current.memberships, [project.id]: event.target.value as "Contributor" | "Viewer" } }))} className="mt-2 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface-2)] px-2 py-1.5 text-xs"><option value="Contributor">Contributor</option><option value="Viewer">Viewer</option></select> : null}
                  </div>
                );
              })}
            </div>
          </fieldset>

          <div className="mt-6 flex justify-end border-t border-[var(--color-border)] pt-5">
            <button disabled={busy || (!creating && !selectedUser)} type="submit" className="app-button-primary">{busy ? "Saving…" : creating ? "Create user" : "Save user"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
