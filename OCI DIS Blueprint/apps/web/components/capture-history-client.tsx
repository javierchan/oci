"use client";

/* Client-side manual capture history with direct removal actions. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";
import { ListChecks, Upload, Wand2 } from "lucide-react";

import { ConfirmModal } from "@/components/modal";
import { emitToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { AuditEvent } from "@/lib/types";

type CaptureHistoryClientProps = {
  projectId: string;
  initialEvents: AuditEvent[];
};

function integrationLabel(event: AuditEvent): string {
  const payload = event.new_value;
  if (payload && typeof payload === "object") {
    const interfaceName = payload.interface_name;
    const interfaceId = payload.interface_id;
    if (typeof interfaceName === "string" && interfaceName.trim()) {
      return interfaceName;
    }
    if (typeof interfaceId === "string" && interfaceId.trim()) {
      return interfaceId;
    }
  }
  return event.entity_id;
}

export function CaptureHistoryClient({
  projectId,
  initialEvents,
}: CaptureHistoryClientProps): JSX.Element {
  const router = useRouter();
  const [events, setEvents] = useState<AuditEvent[]>(initialEvents);
  const [deletingIntegrationId, setDeletingIntegrationId] = useState<string>("");
  const [deleteTarget, setDeleteTarget] = useState<AuditEvent | null>(null);

  async function handleDelete(event: AuditEvent): Promise<void> {
    setDeletingIntegrationId(event.entity_id);
    try {
      await api.deleteIntegration(projectId, event.entity_id);
      setEvents((current: AuditEvent[]) =>
        current.filter((entry: AuditEvent) => entry.entity_id !== event.entity_id),
      );
      emitToast("success", "Captured integration removed.");
      startTransition(() => {
        router.refresh();
      });
    } catch (caughtError) {
      emitToast("error", caughtError instanceof Error ? caughtError.message : "Unable to remove capture.");
    } finally {
      setDeletingIntegrationId("");
    }
  }

  return (
    <section className="app-table-shell">
      <div className="border-b border-[var(--color-border)] px-6 py-5">
        <p className="app-label">History</p>
        <h2 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">Recent guided captures</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
          Guided capture activity stays auditable here so architects can reopen a draft from catalog detail or safely remove a mistaken manual entry.
        </p>
      </div>
      {events.length === 0 ? (
        <div className="px-6 py-8">
          <div className="rounded-[1.75rem] border border-dashed border-[var(--color-border)] bg-[var(--color-surface)] p-6">
            <div className="max-w-2xl">
              <p className="app-label">Day Zero</p>
              <h3 className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">
                No guided captures yet
              </h3>
              <p className="mt-3 text-sm leading-6 text-[var(--color-text-secondary)]">
                This project has not recorded any manual capture activity yet. Start a guided capture for a single integration, import a workbook for bulk intake, or open Catalog once governed rows exist.
              </p>
            </div>

            <div className="mt-6 grid gap-4 lg:grid-cols-3">
              <article className="app-card-muted p-5">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--color-surface)] text-[var(--color-accent)]">
                  <Wand2 className="h-5 w-5" />
                </div>
                <h4 className="mt-4 text-base font-semibold text-[var(--color-text-primary)]">Start guided capture</h4>
                <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
                  Walk through source, flow, and technical details without needing the workbook first.
                </p>
                <Link href={`/projects/${projectId}/capture/new`} className="mt-4 inline-flex app-link">
                  Open the wizard →
                </Link>
              </article>

              <article className="app-card-muted p-5">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--color-surface)] text-[var(--color-accent)]">
                  <Upload className="h-5 w-5" />
                </div>
                <h4 className="mt-4 text-base font-semibold text-[var(--color-text-primary)]">Bulk import workbook</h4>
                <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
                  Use the governed template and import flow when you already have source rows ready for normalization.
                </p>
                <Link href={`/projects/${projectId}/import`} className="mt-4 inline-flex app-link">
                  Open import →
                </Link>
              </article>

              <article className="app-card-muted p-5">
                <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-[var(--color-surface)] text-[var(--color-accent)]">
                  <ListChecks className="h-5 w-5" />
                </div>
                <h4 className="mt-4 text-base font-semibold text-[var(--color-text-primary)]">Review in catalog</h4>
                <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
                  Once the first integrations land, catalog detail becomes the hub for lineage, patching, and recalculation.
                </p>
                <Link href={`/projects/${projectId}/catalog`} className="mt-4 inline-flex app-link">
                  Open catalog →
                </Link>
              </article>
            </div>
          </div>
        </div>
      ) : (
        <table className="min-w-full divide-y divide-[var(--color-table-border)] text-left">
          <thead className="app-table-header">
            <tr>
              <th className="px-6 py-4 font-medium">When</th>
              <th className="px-6 py-4 font-medium">Integration</th>
              <th className="px-6 py-4 font-medium">Actor</th>
              <th className="px-6 py-4 font-medium">Open</th>
              <th className="px-6 py-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-table-border)] text-sm">
            {events.map((event) => (
              <tr key={event.id} className="app-table-row">
                <td className="px-6 py-4 text-[var(--color-text-secondary)]">{formatDate(event.created_at)}</td>
                <td className="px-6 py-4 font-medium text-[var(--color-text-primary)]">{integrationLabel(event)}</td>
                <td className="px-6 py-4 text-[var(--color-text-secondary)]">{event.actor_id}</td>
                <td className="px-6 py-4">
                  <Link
                    href={`/projects/${projectId}/catalog/${event.entity_id}`}
                    className="app-link"
                  >
                    View in Catalog
                  </Link>
                </td>
                <td className="px-6 py-4">
                  <button
                    type="button"
                    onClick={() => {
                      setDeleteTarget(event);
                    }}
                    disabled={deletingIntegrationId === event.entity_id}
                    className="text-sm font-medium text-rose-700 transition hover:text-rose-500 disabled:cursor-not-allowed disabled:text-[var(--color-text-muted)]"
                  >
                    {deletingIntegrationId === event.entity_id ? "Removing…" : "Remove"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <ConfirmModal
        open={deleteTarget !== null}
        title="Remove captured integration"
        description={`"${deleteTarget ? integrationLabel(deleteTarget) : "This integration"}" will be removed from the project.`}
        confirmLabel="Remove integration"
        cancelLabel="Keep it"
        danger
        onConfirm={() => {
          if (deleteTarget) {
            void handleDelete(deleteTarget);
          }
          setDeleteTarget(null);
        }}
        onCancel={() => setDeleteTarget(null)}
      />
    </section>
  );
}
