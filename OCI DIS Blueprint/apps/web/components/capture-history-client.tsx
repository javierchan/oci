"use client";

/* Client-side manual capture history with direct removal actions. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { startTransition, useState } from "react";

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
    if (typeof interfaceId === "string" && interfaceId.trim()) {
      return interfaceId;
    }
    if (typeof interfaceName === "string" && interfaceName.trim()) {
      return interfaceName;
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
  const [error, setError] = useState<string>("");

  async function handleDelete(event: AuditEvent): Promise<void> {
    const label = integrationLabel(event);
    const confirmed = window.confirm(
      `Remove captured integration "${label}" from this project?`,
    );
    if (!confirmed) {
      return;
    }

    setDeletingIntegrationId(event.entity_id);
    setError("");
    try {
      await api.deleteIntegration(projectId, event.entity_id);
      setEvents((current: AuditEvent[]) =>
        current.filter((entry: AuditEvent) => entry.entity_id !== event.entity_id),
      );
      startTransition(() => {
        router.refresh();
      });
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Unable to remove capture.");
    } finally {
      setDeletingIntegrationId("");
    }
  }

  return (
    <section className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-6 py-5">
        <p className="text-xs uppercase tracking-[0.25em] text-slate-500">History</p>
        <h2 className="mt-2 text-2xl font-semibold text-slate-950">Recent guided captures</h2>
      </div>
      {events.length === 0 ? (
        <div className="px-6 py-10 text-sm text-slate-500">
          No manual capture events have been recorded for this project yet.
        </div>
      ) : (
        <table className="min-w-full divide-y divide-slate-200 text-left">
          <thead className="bg-slate-950 text-xs uppercase tracking-[0.25em] text-slate-400">
            <tr>
              <th className="px-6 py-4 font-medium">When</th>
              <th className="px-6 py-4 font-medium">Integration</th>
              <th className="px-6 py-4 font-medium">Actor</th>
              <th className="px-6 py-4 font-medium">Open</th>
              <th className="px-6 py-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 text-sm text-slate-700">
            {events.map((event) => (
              <tr key={event.id}>
                <td className="px-6 py-4 text-slate-500">{formatDate(event.created_at)}</td>
                <td className="px-6 py-4 font-medium text-slate-950">{integrationLabel(event)}</td>
                <td className="px-6 py-4">{event.actor_id}</td>
                <td className="px-6 py-4">
                  <Link
                    href={`/projects/${projectId}/catalog/${event.entity_id}`}
                    className="text-sm font-medium text-sky-700 hover:text-sky-500"
                  >
                    View in Catalog
                  </Link>
                </td>
                <td className="px-6 py-4">
                  <button
                    type="button"
                    onClick={() => {
                      void handleDelete(event);
                    }}
                    disabled={deletingIntegrationId === event.entity_id}
                    className="text-sm font-medium text-rose-700 hover:text-rose-500 disabled:cursor-not-allowed disabled:text-slate-400"
                  >
                    {deletingIntegrationId === event.entity_id ? "Removing…" : "Remove"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {error ? <p className="border-t border-slate-200 px-6 py-4 text-sm text-rose-600">{error}</p> : null}
    </section>
  );
}
