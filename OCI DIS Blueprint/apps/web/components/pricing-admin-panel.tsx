"use client";

/* Operational admin surface for governed OCI price catalogs and SKU mappings. */

import {
  AlertTriangle,
  Check,
  CheckCircle2,
  FileCheck2,
  FileUp,
  Loader2,
  PackageCheck,
  PackageSearch,
  Pencil,
  RefreshCcw,
  Search,
  ShieldCheck,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { emitToast } from "@/hooks/use-toast";
import { OciProductCatalog } from "@/components/oci-product-catalog";
import { OciCoverageReview } from "@/components/oci-coverage-review";
import { api, getErrorMessage } from "@/lib/api";
import { formatDate, formatNumber } from "@/lib/format";
import {
  commercialCandidatePresentation,
  commercialReleaseCoverage,
  isPriceSyncTerminal,
} from "@/lib/types";
import type {
  CommercialCandidate,
  CommercialCandidateDetail,
  CommercialCandidateDecision,
  CommercialCoverageReport,
  CommercialExceptionDecision,
  CommercialWorkspace,
  PriceCatalogSnapshot,
  GovernanceChangeSet,
  PriceItem,
  PriceSource,
  PriceSyncJob,
  SkuMapping,
  SkuMappingPatch,
  SkuMappingStatus,
} from "@/lib/types";

const EMPTY_COMMERCIAL_WORKSPACE: CommercialWorkspace = {
  document: null,
  summary: { skus: 0, candidates: 0, pending: 0, approved: 0, blocked: 0, exceptions: 0 },
  candidates: [],
  page: 1, page_size: 50, total: 0,
  exceptions: [],
  exceptions_page: 1, exceptions_page_size: 50, exceptions_total: 0,
  releases: [],
  field_authority: {},
};

function humanize(value: string): string {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "Not established";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

type CandidateDraft = {
  decision: CommercialCandidateDecision;
  rationale: string;
};

type ExceptionDraft = {
  decision: CommercialExceptionDecision;
  rationale: string;
  target_part_number?: string;
};

function CommercialCatalogWorkspace(): JSX.Element {
  const [workspace, setWorkspace] = useState<CommercialWorkspace>(EMPTY_COMMERCIAL_WORKSPACE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [candidateQuery, setCandidateQuery] = useState("");
  const [candidateStatus, setCandidateStatus] = useState("all");
  const [candidatePage, setCandidatePage] = useState(1);
  const [candidateDetails, setCandidateDetails] = useState<Record<string, CommercialCandidateDetail>>({});
  const [detailLoading, setDetailLoading] = useState<Record<string, boolean>>({});
  const [finalizeRationale, setFinalizeRationale] = useState("");
  const [coverageRationale, setCoverageRationale] = useState("");
  const [coveragePromote, setCoveragePromote] = useState(false);
  const [coveragePreview, setCoveragePreview] = useState<CommercialCoverageReport | null>(null);
  const [candidateDrafts, setCandidateDrafts] = useState<Record<string, CandidateDraft>>({});
  const [exceptionDrafts, setExceptionDrafts] = useState<Record<string, ExceptionDraft>>({});

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    try {
      setWorkspace(await api.getCommercialCatalog({ page: candidatePage, page_size: 50, search: candidateQuery.trim() || undefined, status: candidateStatus }));
      setError("");
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to load official commercial evidence."));
    } finally {
      setLoading(false);
    }
  }, [candidatePage, candidateQuery, candidateStatus]);

  useEffect(() => {
    const search = candidateQuery.trim();
    if (!search) {
      void load();
      return undefined;
    }
    let active = true;
    const timer = window.setTimeout(() => {
      setLoading(true);
      api.getCommercialCatalog({ search, page: candidatePage, page_size: 50, status: candidateStatus })
        .then((result) => {
          if (active) {
            setWorkspace(result);
            setError("");
          }
        })
        .catch((caughtError) => {
          if (active) {
            setError(getErrorMessage(caughtError, "Unable to search the commercial review queue."));
          }
        })
        .finally(() => {
          if (active) {
            setLoading(false);
          }
        });
    }, 250);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [candidatePage, candidateQuery, candidateStatus, load]);
  const visibleCandidates = workspace.candidates;
  const evidenceApproved = workspace.document?.status === "approved_evidence";

  function candidateDraft(candidateId: string): CandidateDraft {
    return candidateDrafts[candidateId] ?? { decision: "keep_blocked", rationale: "" };
  }

  function exceptionDraft(exceptionId: string): ExceptionDraft {
    return exceptionDrafts[exceptionId] ?? { decision: "keep_open", rationale: "" };
  }

  async function runAction(actionKey: string, action: () => Promise<CommercialWorkspace>, success: string): Promise<void> {
    setBusy(actionKey);
    try {
      await action();
      await load();
      setError("");
      emitToast("success", success);
    } catch (caughtError) {
      const message = getErrorMessage(caughtError, "The commercial governance action could not be completed.");
      setError(message);
      emitToast("error", message);
    } finally {
      setBusy(null);
    }
  }

  async function uploadDocument(): Promise<void> {
    if (!uploadFile) {
      return;
    }
    await runAction(
      "commercial-upload",
      () => api.importCommercialDocument(uploadFile),
      "Official workbook imported as immutable review evidence.",
    );
    setUploadFile(null);
  }

  async function reviewCandidate(candidate: CommercialCandidate): Promise<void> {
    const draft = candidateDraft(candidate.id);
    await runAction(
      `candidate:${candidate.id}`,
      () => api.reviewCommercialCandidate(candidate.id, draft),
      `Candidate ${candidate.part_number} decision recorded.`,
    );
  }

  async function revalidateCandidate(candidate: CommercialCandidate): Promise<void> {
    await runAction(
      `revalidate:${candidate.id}`,
      () => api.revalidateCommercialCandidate(candidate.id),
      `Candidate ${candidate.part_number} revalidated against persisted official evidence. Its explicit review decision was not changed.`,
    );
  }

  async function loadCandidateDetail(candidateId: string): Promise<void> {
    if (candidateDetails[candidateId] || detailLoading[candidateId]) return;
    setDetailLoading((current) => ({ ...current, [candidateId]: true }));
    try {
      const detail = await api.getCommercialCandidate(candidateId);
      setCandidateDetails((current) => ({ ...current, [candidateId]: detail }));
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to load commercial candidate detail."));
    } finally {
      setDetailLoading((current) => ({ ...current, [candidateId]: false }));
    }
  }

  async function reviewException(exceptionId: string): Promise<void> {
    const draft = exceptionDraft(exceptionId);
    await runAction(
      `exception:${exceptionId}`,
      () => api.reviewCommercialException(exceptionId, draft),
      "Exception disposition recorded without removing its source evidence.",
    );
  }

  async function finalizeCatalogReview(): Promise<void> {
    if (!workspace.document) {
      return;
    }
    await runAction(
      "finalize-catalog-review",
      () => api.finalizeCommercialCatalogReview(workspace.document!.id, {
        rationale: finalizeRationale.trim(),
      }),
      "Catalog review finalized. Unambiguous SKUs were approved and all remaining SKUs were blocked with governed reasons.",
    );
  }

  async function previewCoverageAdvance(): Promise<void> {
    if (!workspace.document) return;
    setBusy("coverage-preview");
    try {
      const result = await api.advanceCommercialCatalogCoverage(workspace.document.id, {
        rationale: coverageRationale.trim(),
        dry_run: true,
        promote: coveragePromote,
      });
      setWorkspace(result);
      setCoveragePreview(result.coverage_report);
      setError("");
      emitToast("success", "Coverage preview is ready. No governance state was changed.");
    } catch (caughtError) {
      const message = getErrorMessage(caughtError, "Unable to preview catalog coverage.");
      setError(message);
      emitToast("error", message);
    } finally {
      setBusy(null);
    }
  }

  async function confirmCoverageAdvance(): Promise<void> {
    if (!workspace.document || !coveragePreview) return;
    setBusy("coverage-confirm");
    try {
      const result = await api.advanceCommercialCatalogCoverage(workspace.document.id, {
        rationale: coverageRationale.trim(),
        dry_run: false,
        promote: coveragePromote,
      });
      setWorkspace(result);
      setCoveragePreview(result.coverage_report);
      setError("");
      const promotionNote = result.coverage_report.promotion_status === "skipped"
        ? ` Release promotion was skipped: ${result.coverage_report.promotion_detail ?? "preconditions are incomplete"}.`
        : "";
      emitToast("success", `Coverage advanced through deterministic finalization.${promotionNote}`);
    } catch (caughtError) {
      const message = getErrorMessage(caughtError, "Unable to advance catalog coverage.");
      setError(message);
      emitToast("error", message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="app-table-shell min-w-0 overflow-hidden" aria-labelledby="commercial-catalog-title">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--color-border)] px-5 py-5">
        <div className="max-w-3xl">
          <p className="app-label">Official Commercial Catalog</p>
          <h2 id="commercial-catalog-title" className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">
            Evidence, mapping decisions, and releases
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">
            Oracle documents establish commercial meaning. Generated candidates remain proposals until an explicit review decision is recorded; approving evidence never approves mappings or rules.
          </p>
        </div>
        <button className="app-button-secondary gap-2" type="button" disabled={busy !== null || loading} onClick={() => void load()}>
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
          Refresh
        </button>
      </div>

      {error ? (
        <div role="alert" className="border-b border-rose-400/45 bg-[var(--color-surface-2)] px-5 py-4 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </div>
      ) : null}

      <div className="grid gap-px bg-[var(--color-border)] sm:grid-cols-2 xl:grid-cols-4">
        {[
          ["Normalized SKUs", workspace.summary.skus, "Official and structured catalog coverage"],
          ["Generated candidates", workspace.summary.candidates, `${workspace.summary.pending} pending · ${workspace.summary.blocked} truthfully blocked`],
          ["Explicitly approved", workspace.summary.approved, "Mappings and eligible rules with a recorded review decision"],
          ["Open exceptions", workspace.summary.exceptions, "Source conflicts or prerequisites still open"],
        ].map(([label, value, detail]) => (
          <div key={String(label)} className="min-w-0 bg-[var(--color-surface)] px-5 py-4">
            <p className="app-label">{label}</p>
            <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{formatNumber(Number(value))}</p>
            <p className="mt-1 text-xs leading-5 text-[var(--color-text-muted)]">{detail}</p>
          </div>
        ))}
      </div>

      <div className="grid min-w-0 border-t border-[var(--color-border)] xl:grid-cols-[minmax(0,1.45fr)_minmax(22rem,0.55fr)]">
        <div className="min-w-0 border-b border-[var(--color-border)] p-5 xl:border-b-0 xl:border-r">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 max-w-full flex-1">
              <p className="app-label">Latest Official Document</p>
              {workspace.document ? (
                <>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <h3 className="min-w-0 max-w-full [overflow-wrap:anywhere] text-lg font-semibold text-[var(--color-text-primary)]">{workspace.document.original_filename}</h3>
                    <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClasses(workspace.document.status)}`}>
                      {humanize(workspace.document.status)}
                    </span>
                  </div>
                  <dl className="mt-4 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
                    <div><dt className="text-xs text-[var(--color-text-muted)]">Records</dt><dd className="mt-1 font-semibold text-[var(--color-text-primary)]">{formatNumber(workspace.document.record_count)}</dd></div>
                    <div><dt className="text-xs text-[var(--color-text-muted)]">Parser</dt><dd className="mt-1 break-all font-mono text-xs text-[var(--color-text-primary)]">{workspace.document.parser_version}</dd></div>
                    <div><dt className="text-xs text-[var(--color-text-muted)]">Retrieved</dt><dd className="mt-1 text-[var(--color-text-primary)]">{formatDate(workspace.document.retrieved_at)}</dd></div>
                    <div><dt className="text-xs text-[var(--color-text-muted)]">SHA-256</dt><dd className="mt-1 font-mono text-xs text-[var(--color-text-primary)]" title={workspace.document.content_hash}>{compactId(workspace.document.content_hash)}</dd></div>
                  </dl>
                </>
              ) : (
                <p className="mt-2 text-sm text-[var(--color-text-secondary)]">No official Oracle commercial workbook has been imported.</p>
              )}
            </div>
            {workspace.document && !evidenceApproved ? (
              <button className="app-button-primary gap-2" type="button" disabled={busy !== null} onClick={() => void runAction("approve-evidence", () => api.approveCommercialDocument(workspace.document!.id), "Official document approved as evidence. Candidate reviews remain separate.")}>
                {busy === "approve-evidence" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileCheck2 className="h-4 w-4" />}
                Approve evidence
              </button>
            ) : null}
          </div>
          <div className="mt-4 flex items-start gap-3 border-l-2 border-[var(--color-accent)] bg-[var(--color-surface-2)] px-4 py-3">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[var(--color-accent)]" />
            <p className="text-xs leading-5 text-[var(--color-text-secondary)]">
              Evidence approval confirms provenance and parser coverage only. Mapping, rule, exception, price-snapshot, and release approvals remain independent governed decisions.
            </p>
          </div>
        </div>

        <div className="min-w-0 p-5">
          <p className="app-label">Import Official Evidence</p>
          <h3 className="mt-2 text-base font-semibold text-[var(--color-text-primary)]">Price List + Supplement workbook</h3>
          <p className="mt-2 text-xs leading-5 text-[var(--color-text-secondary)]">Upload the Oracle XLSX as a new immutable snapshot. Existing releases remain unchanged.</p>
          <label className="mt-4 block text-sm font-semibold text-[var(--color-text-primary)]">
            XLSX workbook
            <input className="mt-2 block min-w-0 max-w-full text-sm text-[var(--color-text-secondary)] file:mr-3 file:rounded-lg file:border-0 file:bg-[var(--color-surface-3)] file:px-3 file:py-2 file:font-semibold file:text-[var(--color-text-primary)]" type="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
          </label>
          <button className="app-button-secondary mt-4 w-full gap-2" type="button" disabled={!uploadFile || busy !== null} onClick={() => void uploadDocument()}>
            {busy === "commercial-upload" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
            Import official workbook
          </button>
        </div>
      </div>

      <div className="border-t border-[var(--color-border)]">
        <div className="border-b border-[var(--color-border)] px-5 py-4">
          <p className="app-label">Field Authority</p>
          <h3 className="mt-2 text-base font-semibold text-[var(--color-text-primary)]">Which source governs each commercial decision</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="bg-[var(--color-surface-2)] text-xs uppercase tracking-[0.12em] text-[var(--color-text-muted)]"><tr><th className="px-5 py-3">Decision field</th><th className="px-5 py-3">Authoritative source</th><th className="px-5 py-3">Operational use</th></tr></thead>
            <tbody className="divide-y divide-[var(--color-border)]">
              {Object.entries(workspace.field_authority).map(([field, authority]) => (
                <tr key={field}><td className="px-5 py-3 font-medium text-[var(--color-text-primary)]">{humanize(field)}</td><td className="px-5 py-3 text-[var(--color-text-secondary)]">{humanize(authority)}</td><td className="px-5 py-3 text-xs text-[var(--color-text-muted)]">Lower-authority sources may corroborate, but cannot silently replace this value.</td></tr>
              ))}
              {!loading && Object.keys(workspace.field_authority).length === 0 ? <tr><td className="px-5 py-6 text-[var(--color-text-secondary)]" colSpan={3}>Field authority will appear after the commercial catalog service is available.</td></tr> : null}
            </tbody>
          </table>
        </div>
      </div>

      <div className="border-t border-[var(--color-border)]">
        <div className="grid min-w-0 xl:grid-cols-[minmax(0,1.25fr)_minmax(22rem,0.75fr)]">
          <div className="min-w-0 border-b border-[var(--color-border)] px-5 py-5 xl:border-b-0 xl:border-r">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-[var(--color-accent)]" />
              <div className="min-w-0">
                <p className="app-label">Coverage Advancement</p>
                <h3 className="mt-2 text-base font-semibold text-[var(--color-text-primary)]">Safely unlock direct-metered OCI coverage</h3>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
                  Resolve only low-severity product identity naming variance, then apply the existing deterministic review gate. Dependency, metric, term, and repeated-source conflicts remain blocked for individual review.
                </p>
              </div>
            </div>
            {coveragePreview ? (
              <div className="mt-5 overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)]">
                <div className="grid gap-px bg-[var(--color-border)] sm:grid-cols-2 xl:grid-cols-5">
                  {[
                    [coveragePreview.dry_run ? "Would resolve" : "Resolved", coveragePreview.dry_run ? coveragePreview.eligible_open_exceptions : coveragePreview.resolved_exceptions],
                    ["Direct metered ready", coveragePreview.projected_direct_metered_approved],
                    ["Still blocked", coveragePreview.projected_blocked],
                    ["Approved in release", coveragePreview.release_part_number_count],
                    ["Enabled for BOM", coveragePreview.release_bom_part_number_count],
                  ].map(([label, value]) => (
                    <div key={String(label)} className="min-w-0 bg-[var(--color-surface)] px-4 py-3">
                      <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--color-text-muted)]">{label}</p>
                      <p className="mt-1 text-xl font-semibold text-[var(--color-text-primary)]">{formatNumber(Number(value))}</p>
                    </div>
                  ))}
                </div>
                <div className="px-4 py-3 text-xs leading-5 text-[var(--color-text-secondary)]">
                  {coveragePreview.dry_run
                    ? `${formatNumber(coveragePreview.projected_approved)} of ${formatNumber(coveragePreview.candidate_count)} candidates would pass finalization. No records changed.`
                    : `${formatNumber(coveragePreview.current_approved)} candidates are approved after finalization; ${formatNumber(coveragePreview.release_bom_part_number_count)} also have an approved App mapping and can enter a BOM. Promotion: ${humanize(coveragePreview.promotion_status)}.`}
                  {coveragePreview.promotion_detail ? <span className="mt-1 block text-amber-700 dark:text-amber-300">{coveragePreview.promotion_detail}</span> : null}
                </div>
              </div>
            ) : (
              <div className="mt-5 border-l-2 border-[var(--color-accent)] bg-[var(--color-surface-2)] px-4 py-3 text-xs leading-5 text-[var(--color-text-secondary)]">
                Preview computes the exact candidate funnel without mutating exceptions, review dispositions, releases, mappings, or BOMs.
              </div>
            )}
            {coveragePreview && Object.keys(coveragePreview.blockers_by_reason).length > 0 ? (
              <div className="mt-4">
                <p className="app-label">Remaining governed blockers</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(coveragePreview.blockers_by_reason).slice(0, 6).map(([reason, count]) => (
                    <span key={reason} className="app-theme-chip">{humanize(reason)} · {formatNumber(count)}</span>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
          <div className="min-w-0 px-5 py-5">
            <label className="block text-xs font-semibold text-[var(--color-text-secondary)]" htmlFor="coverage-advance-rationale">Governance rationale</label>
            <textarea
              id="coverage-advance-rationale"
              className="mt-2 min-h-24 w-full resize-y rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-sm text-[var(--color-text-primary)]"
              placeholder="Explain why low-risk identity variance can be closed in this official source snapshot."
              value={coverageRationale}
              onChange={(event) => { setCoverageRationale(event.target.value); setCoveragePreview(null); }}
            />
            <label className="mt-3 flex cursor-pointer items-start gap-3 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] px-3 py-3 text-xs leading-5 text-[var(--color-text-secondary)]">
              <input className="mt-1 h-4 w-4 accent-[var(--color-accent)]" type="checkbox" checked={coveragePromote} onChange={(event) => { setCoveragePromote(event.target.checked); setCoveragePreview(null); }} />
              <span><strong className="block text-[var(--color-text-primary)]">Promote release after finalization</strong>Promotion remains gated by approved pricing, structured OCI artifacts, and a validated change set. If incomplete, finalization persists and promotion is truthfully skipped.</span>
            </label>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <button className="app-button-secondary gap-2" type="button" disabled={!workspace.document || !evidenceApproved || coverageRationale.trim().length < 8 || busy !== null} onClick={() => void previewCoverageAdvance()}>
                {busy === "coverage-preview" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                Preview
              </button>
              <button className="app-button-primary gap-2" type="button" disabled={!coveragePreview?.dry_run || busy !== null} onClick={() => void confirmCoverageAdvance()}>
                {busy === "coverage-confirm" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
                Confirm
              </button>
            </div>
            {workspace.document && !evidenceApproved ? <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">Approve official evidence before previewing or advancing coverage.</p> : null}
          </div>
        </div>
      </div>

      <div className="border-t border-[var(--color-border)]">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--color-border)] px-5 py-4">
          <div><p className="app-label">Candidate Review Queue</p><h3 className="mt-2 text-base font-semibold text-[var(--color-text-primary)]">Generated proposals awaiting explicit disposition</h3></div>
          <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row">
            <label className="relative block min-w-0 sm:w-80"><Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-[var(--color-text-muted)]" /><input aria-label="Search commercial candidates" className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] py-2.5 pl-9 pr-3 text-sm" placeholder="Search SKU, product, metric, or family" value={candidateQuery} onChange={(event) => { setCandidateQuery(event.target.value); setCandidatePage(1); }} /></label>
            <select aria-label="Filter candidate status" className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm" value={candidateStatus} onChange={(event) => { setCandidateStatus(event.target.value); setCandidatePage(1); }}><option value="all">All statuses</option><option value="pending_review">Needs review</option><option value="approved">Explicitly approved</option><option value="blocked">Blocked</option></select>
          </div>
        </div>
        <div className="divide-y divide-[var(--color-border)]">
          {visibleCandidates.map((candidate) => {
            const detailCandidate: CommercialCandidateDetail = candidateDetails[candidate.id] ?? {
              ...candidate,
              identity: {
                ...candidate.identity,
                product_hierarchy: [],
                product_paths: [],
                official_location_count: 0,
                structured_product: {},
              },
              commercial_term: candidate.commercial_term ? {
                ...candidate.commercial_term,
                commercial_prices: [],
                additional_information: null,
                notes: null,
                source_sheet: "",
                source_row: 0,
                constraints: [],
              } : null,
              composition: [],
              proposed_mapping: {},
              reasons: [],
            };
            const draft = candidateDraft(candidate.id);
            const presentation = commercialCandidatePresentation(candidate.status);
            const presentationTone = {
              success: "border-emerald-400/45 text-emerald-700 dark:text-emerald-300",
              warning: "border-amber-400/45 text-amber-700 dark:text-amber-300",
              error: "border-rose-400/45 text-rose-700 dark:text-rose-300",
            }[presentation.tone];
            const approvalBlocked = draft.decision === "approve" && !evidenceApproved;
            return (
              <details key={candidate.id} className="group px-5 py-4" onToggle={(event) => {
                if (event.currentTarget.open) void loadCandidateDetail(candidate.id);
              }}>
                <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2"><span className="font-mono text-xs font-semibold text-[var(--color-text-secondary)]">{candidate.part_number}</span><span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${presentationTone}`}>{presentation.label}</span><span className="app-theme-chip">{humanize(candidate.classification)}</span><span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusClasses(candidate.rule_fixture_status ?? "missing")}`}>Fixture: {humanize(candidate.rule_fixture_status ?? "missing")}</span></div>
                    <p className="mt-2 text-sm font-semibold text-[var(--color-text-primary)]">{candidate.identity.display_name}</p>
                    <p className="mt-1 truncate text-xs text-[var(--color-text-muted)]">{candidate.identity.service_category ?? "Official product placement is not established"}</p>
                  </div>
                  <span className="text-xs font-semibold text-[var(--color-text-secondary)] group-open:hidden">Review details</span>
                </summary>
                {detailLoading[candidate.id] && !candidateDetails[candidate.id] ? <div className="mt-4 flex items-center gap-2 border-t border-[var(--color-border)] pt-4 text-sm text-[var(--color-text-secondary)]"><Loader2 className="h-4 w-4 animate-spin" />Loading governed commercial evidence…</div> : <div className="mt-4 grid min-w-0 gap-5 border-t border-[var(--color-border)] pt-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(22rem,0.75fr)]">
                  <div className="min-w-0">
                    <div className="flex items-start gap-3"><PackageSearch className="mt-0.5 h-5 w-5 shrink-0 text-[var(--color-accent)]" /><div className="min-w-0"><p className="app-label">Official product identity</p><h4 className="mt-2 text-base font-semibold text-[var(--color-text-primary)]">{detailCandidate.identity.display_name}</h4><p className="mt-1 font-mono text-xs text-[var(--color-text-muted)]">{detailCandidate.part_number}</p></div></div>
                    <dl className="mt-4 grid gap-x-5 gap-y-3 sm:grid-cols-2">
                      <div><dt className="text-xs text-[var(--color-text-muted)]">Product hierarchy</dt><dd className="mt-1 text-sm font-medium leading-5 text-[var(--color-text-primary)]">{detailCandidate.identity.product_hierarchy.join(" → ") || "Not established"}</dd></div>
                      <div><dt className="text-xs text-[var(--color-text-muted)]">Official workbook locations</dt><dd className="mt-1 text-sm font-medium text-[var(--color-text-primary)]">{formatNumber(detailCandidate.identity.official_location_count)}</dd></div>
                      <div><dt className="text-xs text-[var(--color-text-muted)]">Billing metric</dt><dd className="mt-1 text-sm font-medium text-[var(--color-text-primary)]">{detailCandidate.commercial_term?.metric_name ?? "Not established"}</dd></div>
                      <div><dt className="text-xs text-[var(--color-text-muted)]">Commercial term type</dt><dd className="mt-1 text-sm font-medium text-[var(--color-text-primary)]">{humanize(detailCandidate.commercial_term?.price_type ?? "not established")}</dd></div>
                    </dl>
                    {detailCandidate.commercial_term?.additional_information ? <div className="mt-4 border-t border-[var(--color-border)] pt-4"><p className="app-label">Official billing guidance</p><p className="mt-2 whitespace-pre-line text-sm leading-6 text-[var(--color-text-secondary)]">{detailCandidate.commercial_term.additional_information}</p></div> : null}
                    {detailCandidate.identity.product_paths.length > 1 ? <details className="mt-4 border-t border-[var(--color-border)] pt-4"><summary className="cursor-pointer text-sm font-semibold text-[var(--color-text-secondary)]">Review {formatNumber(detailCandidate.identity.official_location_count)} official placements</summary><ul className="mt-3 space-y-2 text-xs leading-5 text-[var(--color-text-muted)]">{detailCandidate.identity.product_paths.slice(0, 12).map((path, index) => <li key={`${candidate.id}-path-${index}`}>{path.join(" → ")}</li>)}</ul>{detailCandidate.identity.official_location_count > 12 ? <p className="mt-2 text-xs text-[var(--color-text-muted)]">Showing 12 placements; all {formatNumber(detailCandidate.identity.official_location_count)} remain persisted as source evidence.</p> : null}</details> : null}
                    {detailCandidate.composition.length > 0 ? <div className="mt-4 border-t border-[var(--color-border)] pt-4"><p className="app-label">Documented composition</p><ul className="mt-2 space-y-2 text-sm text-[var(--color-text-secondary)]">{detailCandidate.composition.map((relationship, index) => <li key={`${candidate.id}-relationship-${index}`}><span className="font-semibold text-[var(--color-text-primary)]">{humanize(relationship.relationship_type)}:</span> {relationship.target_name}{relationship.target_part_number ? ` (${relationship.target_part_number})` : ""}</li>)}</ul></div> : null}
                    <div className="mt-5 border-t border-[var(--color-border)] pt-4"><p className="app-label">Proposed commercial behavior</p><dl className="mt-3 grid gap-x-5 gap-y-3 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(detailCandidate.proposed_mapping).filter(([key]) => key !== "field_authority").map(([key, value]) => <div key={key}><dt className="text-xs text-[var(--color-text-muted)]">{humanize(key)}</dt><dd className="mt-1 break-words text-sm font-medium text-[var(--color-text-primary)]">{displayValue(value)}</dd></div>)}</dl></div>
                    <p className="app-label mt-5">Why it was generated</p><ul className="mt-2 space-y-1 text-sm leading-5 text-[var(--color-text-secondary)]">{detailCandidate.reasons.map((reason, index) => <li key={`${candidate.id}-reason-${index}`}>• {displayValue(reason)}</li>)}</ul>
                  </div>
                  <div className="min-w-0 border-l-0 border-[var(--color-border)] xl:border-l xl:pl-5"><p className="app-label">Deterministic validation</p><p className="mt-2 text-xs leading-5 text-[var(--color-text-secondary)]">Re-run the generated rule and quotation fixture against persisted official evidence. This action never approves the candidate.</p><button className="app-button-secondary mt-3 w-full gap-2" type="button" disabled={busy !== null} onClick={() => void revalidateCandidate(candidate)}>{busy === `revalidate:${candidate.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}Revalidate rule</button><div className="my-4 border-t border-[var(--color-border)]" /><p className="app-label">Explicit review decision</p><select aria-label={`Decision for ${candidate.part_number}`} className="mt-3 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm" value={draft.decision} onChange={(event) => setCandidateDrafts((current) => ({ ...current, [candidate.id]: { ...draft, decision: event.target.value as CommercialCandidateDecision } }))}><option value="keep_blocked">Keep blocked</option><option value="approve">Approve mapping and eligible rule</option><option value="reject">Reject proposal</option></select><textarea aria-label={`Rationale for ${candidate.part_number}`} className="mt-3 min-h-24 w-full resize-y rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-sm" placeholder="Document the commercial evidence and decision rationale (minimum 8 characters)." value={draft.rationale} onChange={(event) => setCandidateDrafts((current) => ({ ...current, [candidate.id]: { ...draft, rationale: event.target.value } }))} />{approvalBlocked ? <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">Approve the official document as evidence before approving this candidate.</p> : null}<button className="app-button-primary mt-3 w-full gap-2" type="button" disabled={busy !== null || draft.rationale.trim().length < 8 || approvalBlocked} onClick={() => void reviewCandidate(candidate)}>{busy === `candidate:${candidate.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <CheckCircle2 className="h-4 w-4" />}Record decision</button></div>
                </div>}
              </details>
            );
          })}
          {!loading && visibleCandidates.length === 0 ? <p className="px-5 py-8 text-sm text-[var(--color-text-secondary)]">No candidates match the current search and status filter.</p> : null}
        </div>
        {workspace.total > 0 ? <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--color-border)] px-5 py-4 text-sm text-[var(--color-text-secondary)]"><span>Page {workspace.page} of {Math.max(1, Math.ceil(workspace.total / workspace.page_size))} · {formatNumber(workspace.total)} candidates</span><div className="flex gap-2"><button className="app-button-secondary" type="button" disabled={loading || workspace.page <= 1} onClick={() => setCandidatePage((current) => Math.max(1, current - 1))}>Previous</button><button className="app-button-secondary" type="button" disabled={loading || workspace.page >= Math.ceil(workspace.total / workspace.page_size)} onClick={() => setCandidatePage((current) => current + 1)}>Next</button></div></div> : null}
      </div>

      <div className="border-t border-[var(--color-border)]">
        <div className="border-b border-[var(--color-border)] px-5 py-4"><p className="app-label">Commercial Exceptions</p><h3 className="mt-2 text-base font-semibold text-[var(--color-text-primary)]">Resolve, accept risk, or preserve as open</h3><p className="mt-2 text-xs leading-5 text-[var(--color-text-secondary)]">Every decision keeps the original discrepancy and requires a reviewer rationale.</p></div>
        <div className="divide-y divide-[var(--color-border)]">
          {workspace.exceptions.map((exception) => {
            const draft = exceptionDraft(exception.id);
            const closureBlocked = draft.decision !== "keep_open" && !evidenceApproved;
            const dependency = exception.code === "DEPENDENCY_UNRESOLVED";
            const targetRequired = dependency && draft.decision === "resolve";
            return (
              <div key={exception.id} className="grid min-w-0 gap-4 px-5 py-4 xl:grid-cols-[minmax(0,1fr)_minmax(22rem,0.65fr)]">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <AlertTriangle className={`h-4 w-4 ${exception.severity === "blocking" || exception.severity === "high" ? "text-rose-600 dark:text-rose-300" : "text-amber-600 dark:text-amber-300"}`} />
                    <span className="font-semibold text-[var(--color-text-primary)]">{humanize(exception.code)}</span>
                    <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusClasses(exception.status)}`}>{humanize(exception.status)}</span>
                  </div>
                  <p className="mt-2 font-mono text-xs text-[var(--color-text-muted)]">{exception.part_number ?? "Catalog-level exception"}</p>
                  <dl className="mt-3 grid gap-x-5 gap-y-2 sm:grid-cols-2">
                    {Object.entries(exception.details).map(([key, value]) => <div key={key}><dt className="text-xs text-[var(--color-text-muted)]">{humanize(key)}</dt><dd className="mt-1 break-words text-sm text-[var(--color-text-secondary)]">{displayValue(value)}</dd></div>)}
                  </dl>
                </div>
                <div className="min-w-0">
                  <select aria-label={`Disposition for exception ${exception.code}`} className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 text-sm" value={draft.decision} onChange={(event) => setExceptionDrafts((current) => ({ ...current, [exception.id]: { ...draft, decision: event.target.value as CommercialExceptionDecision } }))}>
                    <option value="keep_open">Keep open</option>
                    <option value="resolve">Resolve with evidence</option>
                    {!dependency ? <option value="accept_risk">Accept documented risk</option> : null}
                  </select>
                  {targetRequired ? (
                    <div className="mt-3">
                      <label className="text-xs font-semibold text-[var(--color-text-secondary)]" htmlFor={`dependency-target-${exception.id}`}>Required OCI part number</label>
                      <input id={`dependency-target-${exception.id}`} className="mt-1 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2.5 font-mono text-sm uppercase" placeholder="B95702" value={draft.target_part_number ?? ""} onChange={(event) => setExceptionDrafts((current) => ({ ...current, [exception.id]: { ...draft, target_part_number: event.target.value.toUpperCase() } }))} />
                      <p className="mt-1 text-xs leading-5 text-[var(--color-text-muted)]">The target must exist in this same official source set and have an approved candidate.</p>
                    </div>
                  ) : null}
                  <textarea aria-label={`Rationale for exception ${exception.code}`} className="mt-3 min-h-20 w-full resize-y rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-sm" placeholder="Explain why this disposition is valid (minimum 8 characters)." value={draft.rationale} onChange={(event) => setExceptionDrafts((current) => ({ ...current, [exception.id]: { ...draft, rationale: event.target.value } }))} />
                  {closureBlocked ? <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">Evidence approval is required before closing or accepting this exception.</p> : null}
                  <button className="app-button-secondary mt-3 w-full gap-2" type="button" disabled={busy !== null || draft.rationale.trim().length < 8 || closureBlocked || (targetRequired && !draft.target_part_number?.trim())} onClick={() => void reviewException(exception.id)}>
                    {busy === `exception:${exception.id}` ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}
                    Record disposition
                  </button>
                </div>
              </div>
            );
          })}
          {!loading && workspace.exceptions.length === 0 ? <p className="px-5 py-8 text-sm text-[var(--color-text-secondary)]">No commercial exceptions are recorded for this document.</p> : null}
        </div>
      </div>

      <div className="grid min-w-0 border-t border-[var(--color-border)] xl:grid-cols-[minmax(0,1fr)_24rem]">
        <div className="min-w-0 border-b border-[var(--color-border)] xl:border-b-0 xl:border-r">
          <div className="border-b border-[var(--color-border)] px-5 py-4"><p className="app-label">Release History</p><h3 className="mt-2 text-base font-semibold text-[var(--color-text-primary)]">Global governed commercial baselines</h3><p className="mt-2 text-xs leading-5 text-[var(--color-text-secondary)]">Each release separates total catalog disposition from quote-ready coverage and current App mappings.</p></div>
          <div className="divide-y divide-[var(--color-border)]">
            {workspace.releases.map((release) => {
              const coverage = commercialReleaseCoverage(release);
              return (
                <article key={release.id} className="min-w-0 px-5 py-4">
                  <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0"><p className="break-words font-mono text-sm font-semibold text-[var(--color-text-primary)]">{release.version}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">{release.approved_at ? `Approved ${formatDate(release.approved_at)}` : "Not approved"}</p></div>
                    <div className="flex flex-wrap items-center gap-2"><span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${statusClasses(release.status)}`}>{humanize(release.status)}</span><span className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${statusClasses(release.validation_status)}`}>{humanize(release.validation_status)}</span><span className="app-theme-chip">{coverage.isGlobal ? "Global catalog" : "Legacy App scope"}</span></div>
                  </div>
                  <dl className="mt-4 grid min-w-0 grid-cols-2 gap-px overflow-hidden rounded-lg bg-[var(--color-border)] lg:grid-cols-4">
                    {[["Catalog total", coverage.catalogTotal], ["Quote-ready", coverage.quoteReady], ["Blocked", coverage.blocked], ["BOM-enabled", coverage.appBomEnabled]].map(([label, value]) => <div key={String(label)} className="min-w-0 bg-[var(--color-surface-2)] px-3 py-3"><dt className="text-[11px] uppercase tracking-[0.12em] text-[var(--color-text-muted)]">{label}</dt><dd className="mt-1 text-lg font-semibold text-[var(--color-text-primary)]">{formatNumber(Number(value))}</dd></div>)}
                  </dl>
                  <div className="mt-3 flex min-w-0 flex-wrap items-center justify-between gap-2 text-xs text-[var(--color-text-muted)]"><span>{release.open_exception_count} open exception{release.open_exception_count === 1 ? "" : "s"} in release scope</span><span>{coverage.excludedMappings} reviewed App mapping{coverage.excludedMappings === 1 ? "" : "s"} excluded from BOM</span>{coverage.blockedParts.length ? <span className="max-w-full break-words font-mono" title={coverage.blockedParts.join(", ")}>{coverage.blockedParts.length} blocked SKU{coverage.blockedParts.length === 1 ? "" : "s"} retained with reasons</span> : null}</div>
                </article>
              );
            })}
            {!loading && workspace.releases.length === 0 ? <p className="px-5 py-6 text-sm text-[var(--color-text-secondary)]">No commercial release has been promoted.</p> : null}
          </div>
        </div>
        <div className="min-w-0 p-5"><ShieldCheck className="h-5 w-5 text-[var(--color-accent)]" /><p className="app-label mt-3">Catalog Review Gate</p><h3 className="mt-2 text-base font-semibold text-[var(--color-text-primary)]">Finalize catalog review</h3><p className="mt-2 text-xs leading-5 text-[var(--color-text-secondary)]">Approve only unambiguous SKUs backed by passing deterministic fixtures. Every other SKU is kept visible and blocked with governed reasons.</p><div className="mt-3 border-l-2 border-[var(--color-accent)] bg-[var(--color-surface-2)] px-3 py-2.5 text-xs leading-5 text-[var(--color-text-secondary)]">This action does not resolve exceptions and does not modify any BOM, price total, or deployment scenario.</div><label className="mt-4 block text-xs font-semibold text-[var(--color-text-secondary)]" htmlFor="commercial-finalize-rationale">Review rationale</label><textarea id="commercial-finalize-rationale" className="mt-2 min-h-24 w-full resize-y rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-3 text-sm text-[var(--color-text-primary)]" placeholder="Explain why the deterministic catalog disposition can be recorded (minimum 8 characters)." value={finalizeRationale} onChange={(event) => setFinalizeRationale(event.target.value)} /><button className="app-button-primary mt-3 w-full gap-2" type="button" disabled={!workspace.document || !evidenceApproved || finalizeRationale.trim().length < 8 || busy !== null} onClick={() => void finalizeCatalogReview()}>{busy === "finalize-catalog-review" ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}Finalize catalog review</button>{workspace.document && !evidenceApproved ? <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">Approve official evidence before finalizing catalog review.</p> : null}<div className="my-5 border-t border-[var(--color-border)]" /><PackageCheck className="h-5 w-5 text-[var(--color-accent)]" /><p className="app-label mt-3">Promotion Gate</p><h3 className="mt-2 text-base font-semibold text-[var(--color-text-primary)]">Promote reviewed release</h3><p className="mt-2 text-xs leading-5 text-[var(--color-text-secondary)]">The backend verifies terminal catalog dispositions, approved official evidence, quote-ready rules, App mappings, and scoped exceptions atomically. A blocked promotion changes nothing.</p><button className="app-button-secondary mt-4 w-full gap-2" type="button" disabled={!workspace.document || !evidenceApproved || busy !== null} onClick={() => workspace.document ? void runAction("promote-release", () => api.promoteCommercialRelease(workspace.document!.id), "Commercial release promoted and ready for governed BOM use.") : undefined}>{busy === "promote-release" ? <Loader2 className="h-4 w-4 animate-spin" /> : <PackageCheck className="h-4 w-4" />}Promote release</button></div>
      </div>
    </section>
  );
}

function statusClasses(status: string): string {
  if (["approved", "approved_evidence", "accepted_risk", "completed", "active", "passed", "promoted", "resolved", "no_change", "not_required"].includes(status)) {
    return "border-emerald-400/45 text-emerald-700 dark:text-emerald-300";
  }
  if (["failed", "retired", "blocked"].includes(status)) {
    return "border-rose-400/45 text-rose-700 dark:text-rose-300";
  }
  return "border-amber-400/45 text-amber-700 dark:text-amber-300";
}

function compactId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 8)}…` : value;
}

type MappingDraft = {
  partNumber: string;
  status: SkuMappingStatus;
  predicates: string;
  quantityBehavior: SkuMapping["quantity_behavior"];
  quantityIncrement: number;
  minimumQuantity: number;
  quantityUnit: string;
  selectionPolicy: SkuMapping["selection_policy"];
};

export function PricingAdminPanel(): JSX.Element {
  const [sources, setSources] = useState<PriceSource[]>([]);
  const [jobs, setJobs] = useState<PriceSyncJob[]>([]);
  const [snapshots, setSnapshots] = useState<PriceCatalogSnapshot[]>([]);
  const [changeSets, setChangeSets] = useState<GovernanceChangeSet[]>([]);
  const [mappings, setMappings] = useState<SkuMapping[]>([]);
  const [items, setItems] = useState<PriceItem[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string>("");
  const [itemSearch, setItemSearch] = useState<string>("");
  const [currency, setCurrency] = useState<string>("USD");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [rateCardName, setRateCardName] = useState<string>("Customer contract rate card");
  const [editingMappingId, setEditingMappingId] = useState<string | null>(null);
  const [mappingDraft, setMappingDraft] = useState<MappingDraft | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string>("");

  const load = useCallback(async (silent = false): Promise<void> => {
    if (!silent) {
      setLoading(true);
    }
    try {
      const [sourceResult, jobResult, snapshotResult, mappingResult, changeSetResult] = await Promise.all([
        api.listPriceSources(),
        api.listPriceSyncJobs(12),
        api.listPriceCatalogSnapshots(12),
        api.listSkuMappings(),
        api.listGovernanceChangeSets(12),
      ]);
      setSources(sourceResult.sources);
      setJobs(jobResult.jobs);
      setSnapshots(snapshotResult.snapshots);
      setMappings(mappingResult.mappings);
      setChangeSets(changeSetResult.change_sets);
      setSelectedSnapshotId((current) => current || snapshotResult.snapshots[0]?.id || "");
      setError("");
    } catch (caughtError) {
      setError(getErrorMessage(caughtError, "Unable to load governed pricing."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const hasActiveJob = useMemo(
    () => jobs.some((job) => !isPriceSyncTerminal(job.status)),
    [jobs],
  );

  useEffect(() => {
    if (!hasActiveJob) {
      return undefined;
    }
    const timer = window.setInterval(() => void load(true), 3000);
    return () => window.clearInterval(timer);
  }, [hasActiveJob, load]);

  useEffect(() => {
    let active = true;
    if (!selectedSnapshotId) {
      setItems([]);
      return () => {
        active = false;
      };
    }
    const timer = window.setTimeout(() => {
      api
        .listPriceItems(selectedSnapshotId, { search: itemSearch || undefined, page: 1, page_size: 100 })
        .then((result) => {
          if (active) {
            setItems(result.items);
          }
        })
        .catch((caughtError) => {
          if (active) {
            setError(getErrorMessage(caughtError, "Unable to load normalized price items."));
          }
        });
    }, 200);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [itemSearch, selectedSnapshotId]);

  async function runSync(): Promise<void> {
    setBusyAction("sync");
    try {
      const publicSource = sources.find((source) => source.source_type === "public_list");
      if (!publicSource) {
        throw new Error("No active Oracle public price source is configured.");
      }
      await api.createPriceSyncJob({ source_id: publicSource.id, currency: currency.toUpperCase() });
      emitToast("info", "Price synchronization queued.");
      await load(true);
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to start price synchronization."));
    } finally {
      setBusyAction(null);
    }
  }

  async function uploadRateCard(): Promise<void> {
    if (!uploadFile) {
      return;
    }
    setBusyAction("upload");
    try {
      const snapshot = await api.importPriceRateCard(uploadFile, rateCardName.trim(), currency.toUpperCase());
      setSelectedSnapshotId(snapshot.id);
      setUploadFile(null);
      emitToast("success", "Rate card imported into an immutable snapshot.");
      await load(true);
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to import the rate card."));
    } finally {
      setBusyAction(null);
    }
  }

  async function approveSnapshot(snapshotId: string): Promise<void> {
    setBusyAction(snapshotId);
    try {
      await api.approvePriceCatalogSnapshot(snapshotId);
      emitToast("success", "Price catalog approved for governed estimates.");
      await load(true);
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to approve the price catalog."));
    } finally {
      setBusyAction(null);
    }
  }

  function startMappingEdit(mapping: SkuMapping): void {
    setEditingMappingId(mapping.id);
    setMappingDraft({
      partNumber: mapping.part_number ?? "",
      status: mapping.status,
      predicates: JSON.stringify(mapping.predicates, null, 2),
      quantityBehavior: mapping.quantity_behavior,
      quantityIncrement: mapping.quantity_increment,
      minimumQuantity: mapping.minimum_quantity,
      quantityUnit: mapping.quantity_unit,
      selectionPolicy: mapping.selection_policy,
    });
  }

  async function saveMapping(mapping: SkuMapping): Promise<void> {
    if (!mappingDraft) {
      return;
    }
    let predicates: Record<string, unknown>;
    try {
      predicates = JSON.parse(mappingDraft.predicates) as Record<string, unknown>;
    } catch {
      emitToast("error", "Predicates must be a valid JSON object.");
      return;
    }
    setBusyAction(mapping.id);
    const patch: SkuMappingPatch = {
      part_number: mappingDraft.partNumber.trim() || null,
      status: mappingDraft.status,
      predicates,
      quantity_behavior: mappingDraft.quantityBehavior,
      quantity_increment: mappingDraft.quantityIncrement,
      minimum_quantity: mappingDraft.minimumQuantity,
      quantity_unit: mappingDraft.quantityUnit.trim(),
      selection_policy: mappingDraft.selectionPolicy,
    };
    try {
      const updated = await api.patchSkuMapping(mapping.id, patch);
      setMappings((current) => current.map((entry) => (entry.id === updated.id ? updated : entry)));
      setEditingMappingId(null);
      setMappingDraft(null);
      emitToast("success", "SKU mapping updated and audited.");
    } catch (caughtError) {
      emitToast("error", getErrorMessage(caughtError, "Unable to update the SKU mapping."));
    } finally {
      setBusyAction(null);
    }
  }

  const approvedMappings = mappings.filter((mapping) => mapping.status === "approved").length;
  const latestChangeSet = changeSets[0];

  return (
    <div className="min-w-0 space-y-5">
      <OciProductCatalog />
      <OciCoverageReview />
      <CommercialCatalogWorkspace />

      {error ? (
        <div role="alert" className="rounded-lg border border-rose-400/45 bg-[var(--color-surface-2)] p-4 text-sm text-rose-700 dark:text-rose-300">
          {error}
        </div>
      ) : null}

      <section className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(20rem,0.7fr)]">
        <div className="app-card min-w-0 p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <p className="app-label">Provider Status</p>
              <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Governed price sources</h2>
            </div>
            <button className="app-button-primary gap-2" type="button" disabled={busyAction !== null || hasActiveJob || !sources.some((source) => source.source_type === "public_list")} onClick={() => void runSync()}>
              {busyAction === "sync" || hasActiveJob ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCcw className="h-4 w-4" />}
              {hasActiveJob ? "Sync running" : "Sync public prices"}
            </button>
          </div>
          <div className="mt-5 grid gap-3 sm:hidden">
            {sources.map((source) => (
              <article key={source.id} className="rounded-lg border border-[var(--color-border)] p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="break-words font-semibold text-[var(--color-text-primary)]">{source.name}</p>
                    <p className="mt-1 text-xs capitalize text-[var(--color-text-muted)]">
                      {source.source_type.replace(/_/g, " ")} · {source.currency}
                    </p>
                  </div>
                  <span className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClasses(source.status)}`}>{source.status}</span>
                </div>
                <p className="mt-3 text-xs text-[var(--color-text-secondary)]">
                  Last sync: {source.last_synced_at ? formatDate(source.last_synced_at) : "Never"}
                </p>
              </article>
            ))}
          </div>
          <div className="mt-5 hidden overflow-x-auto sm:block">
            <table className="w-full min-w-[620px] text-left text-sm">
              <thead className="text-xs uppercase tracking-[0.12em] text-[var(--color-text-muted)]">
                <tr><th className="pb-3">Source</th><th className="pb-3">Type</th><th className="pb-3">Currency</th><th className="pb-3">Status</th><th className="pb-3">Last sync</th></tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {sources.map((source) => (
                  <tr key={source.id}>
                    <td className="py-3 font-semibold text-[var(--color-text-primary)]">{source.name}</td>
                    <td className="py-3 text-[var(--color-text-secondary)]">{source.source_type.replace(/_/g, " ")}</td>
                    <td className="py-3 font-mono text-[var(--color-text-secondary)]">{source.currency}</td>
                    <td className="py-3"><span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClasses(source.status)}`}>{source.status}</span></td>
                    <td className="py-3 text-[var(--color-text-muted)]">{source.last_synced_at ? formatDate(source.last_synced_at) : "Never"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="app-card min-w-0 overflow-hidden p-5">
          <p className="app-label">Contract Rate Card</p>
          <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Import reviewed CSV</h2>
          <p className="mt-2 text-sm leading-6 text-[var(--color-text-secondary)]">Creates an immutable commercial source without replacing public list prices.</p>
          <label className="mt-4 block text-sm font-semibold text-[var(--color-text-primary)]">
            Source name
            <input className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2" value={rateCardName} onChange={(event) => setRateCardName(event.target.value)} />
          </label>
          <label className="mt-3 block text-sm font-semibold text-[var(--color-text-primary)]">
            Currency
            <input className="mt-2 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-3 py-2" maxLength={3} value={currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} />
          </label>
          <label className="mt-3 block text-sm font-semibold text-[var(--color-text-primary)]">
            CSV rate card
            <input className="mt-2 block min-w-0 max-w-full text-sm text-[var(--color-text-secondary)] file:mr-3 file:rounded-lg file:border-0 file:bg-[var(--color-surface-3)] file:px-3 file:py-2 file:font-semibold file:text-[var(--color-text-primary)]" type="file" accept=".csv,text/csv" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} />
          </label>
          <button className="app-button-secondary mt-4 w-full gap-2" type="button" disabled={!uploadFile || !rateCardName.trim() || busyAction !== null} onClick={() => void uploadRateCard()}>
            {busyAction === "upload" ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
            Import rate card
          </button>
        </div>
      </section>

      <section className="app-card min-w-0 overflow-hidden">
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[var(--color-border)] px-5 py-5">
          <div>
            <p className="app-label">OCI Verification Center</p>
            <h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Official sources and quote regressions</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
              Products, metrics, presets, and public prices are captured together. A catalog can be promoted only after every governed commercial family passes its deterministic fixture.
            </p>
          </div>
          {latestChangeSet ? (
            <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${statusClasses(latestChangeSet.validation_status)}`}>
              {latestChangeSet.validation_status.replaceAll("_", " ")}
            </span>
          ) : null}
        </div>
        {latestChangeSet ? (
          <div className="grid gap-px bg-[var(--color-border)] md:grid-cols-4">
            <div className="bg-[var(--color-surface)] p-5">
              <p className="app-label">Source evidence</p>
              <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{latestChangeSet.artifacts.length} / 4</p>
              <p className="mt-1 text-sm text-[var(--color-text-secondary)]">verified artifacts in Object Storage</p>
            </div>
            <div className="bg-[var(--color-surface)] p-5">
              <p className="app-label">Quote coverage</p>
              <p className="mt-2 text-2xl font-semibold text-[var(--color-text-primary)]">{String(latestChangeSet.regression_summary.coverage_pct ?? 0)}%</p>
              <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{String(latestChangeSet.regression_summary.passed ?? 0)} of {String(latestChangeSet.regression_summary.families ?? 0)} families passed</p>
            </div>
            <div className="bg-[var(--color-surface)] p-5">
              <p className="app-label">Detected drift</p>
              <p className="mt-2 text-lg font-semibold capitalize text-[var(--color-text-primary)]">{latestChangeSet.drift_classification.replaceAll("_", " ")}</p>
              <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{String(latestChangeSet.drift_summary.price_signature_changes ?? 0)} price signature changes</p>
            </div>
            <div className="bg-[var(--color-surface)] p-5">
              <p className="app-label">Promotion</p>
              <p className="mt-2 text-lg font-semibold capitalize text-[var(--color-text-primary)]">{latestChangeSet.approval_status.replaceAll("_", " ")}</p>
              <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{formatDate(latestChangeSet.created_at)} · {latestChangeSet.trigger_type}</p>
            </div>
          </div>
        ) : (
          <div className="px-5 py-8 text-sm text-[var(--color-text-secondary)]">
            Run public-source verification to establish the first governed baseline.
          </div>
        )}
        {changeSets.length > 0 ? (
          <div className="border-t border-[var(--color-border)] px-5 py-4">
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {changeSets.slice(0, 6).map((changeSet) => (
                <div key={changeSet.id} className="rounded-lg border border-[var(--color-border)] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-mono text-xs text-[var(--color-text-muted)]">{compactId(changeSet.id)}</span>
                    <span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusClasses(changeSet.validation_status)}`}>{changeSet.status.replaceAll("_", " ")}</span>
                  </div>
                  <p className="mt-2 text-sm font-semibold capitalize text-[var(--color-text-primary)]">{changeSet.drift_classification.replaceAll("_", " ")}</p>
                  <p className="mt-1 text-xs text-[var(--color-text-muted)]">{changeSet.artifacts.length} sources · {String(changeSet.regression_summary.passed ?? 0)} families passed</p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </section>

      <section className="app-card min-w-0 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><p className="app-label">Immutable Catalogs</p><h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Review and approval queue</h2></div>
          <span className="text-sm text-[var(--color-text-secondary)]">{snapshots.length} recent snapshots</span>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {snapshots.map((snapshot) => (
            <div key={snapshot.id} className={`rounded-lg border p-4 ${selectedSnapshotId === snapshot.id ? "border-[var(--color-accent)]" : "border-[var(--color-border)]"}`}>
              <button type="button" className="w-full text-left" onClick={() => setSelectedSnapshotId(snapshot.id)}>
                <div className="flex items-center justify-between gap-3"><span className="font-mono text-xs text-[var(--color-text-muted)]">{compactId(snapshot.id)}</span><span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusClasses(snapshot.approval_status)}`}>{snapshot.approval_status.replace(/_/g, " ")}</span></div>
                <p className="mt-3 text-2xl font-semibold text-[var(--color-text-primary)]">{formatNumber(snapshot.item_count)} items</p>
                <p className="mt-1 text-xs text-[var(--color-text-muted)]">{snapshot.currency} · {formatDate(snapshot.retrieved_at)}</p>
              </button>
              {snapshot.approval_status !== "approved" && snapshot.approval_status !== "superseded" ? <button type="button" className="app-button-secondary mt-4 w-full gap-2" disabled={busyAction !== null || changeSets.find((item) => item.price_snapshot_id === snapshot.id)?.validation_status !== "passed"} onClick={() => void approveSnapshot(snapshot.id)}>{busyAction === snapshot.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}Approve verified change</button> : null}
            </div>
          ))}
          {!loading && snapshots.length === 0 ? <p className="text-sm text-[var(--color-text-secondary)]">No price snapshots exist yet.</p> : null}
        </div>
      </section>

      <section className="app-table-shell min-w-0 overflow-hidden">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[var(--color-border)] px-5 py-4">
          <div><p className="app-label">Normalized Price Items</p><h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Selected catalog evidence</h2></div>
          <label className="relative block w-full min-w-0 text-sm sm:w-auto sm:min-w-[18rem]"><Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-[var(--color-text-muted)]" /><input aria-label="Search price items" className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] py-2.5 pl-9 pr-3" placeholder="Part number, product or metric" value={itemSearch} onChange={(event) => setItemSearch(event.target.value)} /></label>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] text-left text-sm"><thead className="bg-[var(--color-surface-2)] text-xs uppercase tracking-[0.12em] text-[var(--color-text-muted)]"><tr><th className="px-5 py-3">Part number</th><th className="px-5 py-3">Product</th><th className="px-5 py-3">Metric</th><th className="px-5 py-3">Model</th><th className="px-5 py-3 text-right">Unit price</th><th className="px-5 py-3">Tier</th></tr></thead><tbody className="divide-y divide-[var(--color-border)]">{items.map((item) => <tr key={item.id}><td className="px-5 py-3 font-mono text-[var(--color-text-primary)]">{item.part_number}</td><td className="px-5 py-3 font-medium text-[var(--color-text-primary)]">{item.display_name}</td><td className="px-5 py-3 text-[var(--color-text-secondary)]">{item.metric_name}</td><td className="px-5 py-3 text-[var(--color-text-secondary)]">{item.model}</td><td className="px-5 py-3 text-right font-mono text-[var(--color-text-primary)]">{item.currency} {item.value.toFixed(6)}</td><td className="px-5 py-3 text-[var(--color-text-muted)]">{item.range_min ?? "–"} to {item.range_max ?? "∞"}</td></tr>)}</tbody></table>
        </div>
      </section>

      <section className="app-table-shell min-w-0 overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--color-border)] px-5 py-4"><div><p className="app-label">SKU Mapping Coverage</p><h2 className="mt-2 text-xl font-semibold text-[var(--color-text-primary)]">Service demand to commercial SKU</h2></div><p className="text-sm font-semibold text-[var(--color-text-primary)]">{approvedMappings} of {mappings.length} approved</p></div>
        <div className="overflow-x-auto"><table className="w-full min-w-[1050px] text-left text-sm"><thead className="bg-[var(--color-surface-2)] text-xs uppercase tracking-[0.12em] text-[var(--color-text-muted)]"><tr><th className="px-5 py-3">Service / tool</th><th className="px-5 py-3">Part number</th><th className="px-5 py-3">Metric / formula</th><th className="px-5 py-3">Predicates</th><th className="px-5 py-3">Status</th><th className="px-5 py-3 text-right">Action</th></tr></thead><tbody className="divide-y divide-[var(--color-border)]">{mappings.map((mapping) => {
          const editing = editingMappingId === mapping.id && mappingDraft !== null;
          return <tr key={mapping.id} className="align-top"><td className="px-5 py-4"><p className="font-semibold text-[var(--color-text-primary)]">{mapping.service_id}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">{mapping.tool_key}</p></td><td className="px-5 py-4">{editing ? <input aria-label={`Part number for ${mapping.tool_key}`} className="w-36 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2 font-mono" value={mappingDraft.partNumber} onChange={(event) => setMappingDraft({ ...mappingDraft, partNumber: event.target.value })} /> : <span className="font-mono text-[var(--color-text-primary)]">{mapping.part_number ?? "Non-billable"}</span>}</td><td className="min-w-72 px-5 py-4"><p className="text-[var(--color-text-primary)]">{mapping.billing_metric_key}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">{mapping.formula_key}</p>{editing ? <div className="mt-3 grid grid-cols-2 gap-2"><label className="text-xs text-[var(--color-text-muted)]">Rule<select className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5" value={mappingDraft.quantityBehavior} onChange={(event) => setMappingDraft({ ...mappingDraft, quantityBehavior: event.target.value as SkuMapping["quantity_behavior"] })}><option value="packaged">Packaged</option><option value="fixed_capacity">Fixed capacity</option><option value="hourly">Hourly</option><option value="continuous">Continuous</option><option value="manual_monthly">Manual monthly</option></select></label><label className="text-xs text-[var(--color-text-muted)]">Unit<input className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5" value={mappingDraft.quantityUnit} onChange={(event) => setMappingDraft({ ...mappingDraft, quantityUnit: event.target.value })} /></label><label className="text-xs text-[var(--color-text-muted)]">Increment<input type="number" min={0.000001} step="any" className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5" value={mappingDraft.quantityIncrement} onChange={(event) => setMappingDraft({ ...mappingDraft, quantityIncrement: Number(event.target.value) })} /></label><label className="text-xs text-[var(--color-text-muted)]">Minimum<input type="number" min={0} step="any" className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5" value={mappingDraft.minimumQuantity} onChange={(event) => setMappingDraft({ ...mappingDraft, minimumQuantity: Number(event.target.value) })} /></label><label className="col-span-2 text-xs text-[var(--color-text-muted)]">Scenario selection<select className="mt-1 w-full rounded-md border border-[var(--color-border)] bg-[var(--color-surface)] px-2 py-1.5" value={mappingDraft.selectionPolicy} onChange={(event) => setMappingDraft({ ...mappingDraft, selectionPolicy: event.target.value as SkuMapping["selection_policy"] })}><option value="required">Required by default</option><option value="optional">Optional add-on</option><option value="dependent">Dependency-owned</option></select></label></div> : <><p className="mt-2 text-xs text-[var(--color-text-secondary)]">{mapping.quantity_behavior.replaceAll("_", " ")} · {mapping.quantity_increment} increment · {mapping.minimum_quantity} minimum · {mapping.quantity_unit}</p><p className="mt-1 text-xs text-[var(--color-text-muted)]">{mapping.aggregation_window.replaceAll("_", " ")} · {mapping.proration_policy.replaceAll("_", " ")}{mapping.free_tier_scope !== "none" ? ` · free tier ${mapping.free_tier_scope.replaceAll("_", " ")}` : ""}</p><span className="mt-2 inline-flex rounded-full border border-[var(--color-border)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--color-text-muted)]">{mapping.selection_policy.replaceAll("_", " ")}</span></>}</td><td className="max-w-xs px-5 py-4">{editing ? <textarea aria-label={`Predicates for ${mapping.tool_key}`} className="min-h-24 w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-2 font-mono text-xs" value={mappingDraft.predicates} onChange={(event) => setMappingDraft({ ...mappingDraft, predicates: event.target.value })} /> : <code className="break-all text-xs text-[var(--color-text-secondary)]">{JSON.stringify(mapping.predicates)}</code>}</td><td className="px-5 py-4">{editing ? <select aria-label={`Status for ${mapping.tool_key}`} className="rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] px-2.5 py-2" value={mappingDraft.status} onChange={(event) => setMappingDraft({ ...mappingDraft, status: event.target.value as SkuMappingStatus })}><option value="draft">Draft</option><option value="approved">Approved</option><option value="retired">Retired</option></select> : <span className={`rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClasses(mapping.status)}`}>{mapping.status}</span>}</td><td className="px-5 py-4 text-right">{editing ? <div className="flex justify-end gap-2"><button type="button" aria-label={`Cancel editing ${mapping.tool_key}`} className="app-button-secondary h-9 w-9 p-0" onClick={() => { setEditingMappingId(null); setMappingDraft(null); }}><X className="h-4 w-4" /></button><button type="button" aria-label={`Save ${mapping.tool_key}`} className="app-button-primary h-9 w-9 p-0" disabled={busyAction === mapping.id} onClick={() => void saveMapping(mapping)}>{busyAction === mapping.id ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}</button></div> : <button type="button" aria-label={`Edit ${mapping.tool_key}`} className="app-button-secondary h-9 w-9 p-0" onClick={() => startMappingEdit(mapping)}><Pencil className="h-4 w-4" /></button>}</td></tr>;
        })}</tbody></table></div>
      </section>

      {jobs.length > 0 ? <section className="app-card p-5"><p className="app-label">Recent Sync Jobs</p><div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">{jobs.slice(0, 6).map((job) => <div key={job.id} className="rounded-lg border border-[var(--color-border)] p-3"><div className="flex items-center justify-between gap-3"><span className="font-mono text-xs text-[var(--color-text-muted)]">{compactId(job.id)}</span><span className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${statusClasses(job.status)}`}>{job.status}</span></div><p className="mt-2 text-sm text-[var(--color-text-secondary)]">{job.item_count} items · {job.changes_detected} changes</p></div>)}</div></section> : null}
    </div>
  );
}
