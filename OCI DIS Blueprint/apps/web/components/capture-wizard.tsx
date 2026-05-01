"use client";

/* Five-step guided manual capture flow with validation, duplicate checks, and submit handling. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { startTransition, useEffect, useMemo, useState } from "react";
import { z } from "zod";
import { Check } from "lucide-react";

import { CaptureStepDestination } from "@/components/capture-step-destination";
import { CaptureStepIdentity } from "@/components/capture-step-identity";
import { CaptureStepReview } from "@/components/capture-step-review";
import { CaptureStepSource } from "@/components/capture-step-source";
import { CaptureStepTechnical } from "@/components/capture-step-technical";
import { api } from "@/lib/api";
import type {
  DictionaryOption,
  Integration,
  ManualIntegrationCreate,
  PatternDefinition,
} from "@/lib/types";

export type CaptureStepProps = {
  projectId: string;
  form: ManualIntegrationCreate;
  updateField: <K extends keyof ManualIntegrationCreate>(
    _field: K,
    _value: ManualIntegrationCreate[K],
  ) => void;
  patterns: PatternDefinition[];
  toolOptions: DictionaryOption[];
  frequencyOptions: DictionaryOption[];
  triggerTypeOptions: DictionaryOption[];
  complexityOptions: DictionaryOption[];
};

type CaptureWizardProps = {
  projectId: string;
  patterns: PatternDefinition[];
  toolOptions: DictionaryOption[];
  frequencyOptions: DictionaryOption[];
  triggerTypeOptions: DictionaryOption[];
  complexityOptions: DictionaryOption[];
};

const INITIAL_FORM: ManualIntegrationCreate = {
  brand: "",
  business_process: "",
  interface_name: "",
  source_system: "",
  destination_system: "",
  tbq: "Y",
};

const STEP_LABELS = [
  "Identity",
  "Source",
  "Destination",
  "Technical",
  "Review",
] as const;
const STEP_DESCRIPTIONS = [
  "Name and owner",
  "Source system",
  "Destination route",
  "Payload and tools",
  "QA and publish",
] as const;
const SESSION_KEY_PREFIX = "capture-wizard-";

const stepSchemas = [
  z.object({
    brand: z.string().trim().min(1, "Brand is required."),
    business_process: z.string().trim().min(1, "Business process is required."),
    interface_name: z.string().trim().min(1, "Interface name is required."),
  }),
  z.object({
    source_system: z.string().trim().min(1, "Source system is required."),
  }),
  z.object({
    destination_system: z.string().trim().min(1, "Destination system is required."),
  }),
  z.object({}),
  z.object({}),
];

function cleanForm(form: ManualIntegrationCreate): ManualIntegrationCreate {
  return Object.fromEntries(
    Object.entries(form).filter(([, value]) => {
      if (value === undefined) {
        return false;
      }
      if (typeof value === "string") {
        return value.trim().length > 0;
      }
      if (Array.isArray(value)) {
        return value.length > 0;
      }
      return true;
    }),
  ) as ManualIntegrationCreate;
}

export function CaptureWizard({
  projectId,
  patterns,
  toolOptions,
  frequencyOptions,
  triggerTypeOptions,
  complexityOptions,
}: CaptureWizardProps): JSX.Element {
  const router = useRouter();
  const [form, setForm] = useState<ManualIntegrationCreate>(INITIAL_FORM);
  const [currentStep, setCurrentStep] = useState<number>(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [duplicates, setDuplicates] = useState<Integration[]>([]);
  const [duplicateLoading, setDuplicateLoading] = useState<boolean>(false);
  const [submitError, setSubmitError] = useState<string>("");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [createdIntegration, setCreatedIntegration] = useState<Integration | null>(null);
  const [navigationHint, setNavigationHint] = useState<string>("");
  const sessionKey = `${SESSION_KEY_PREFIX}${projectId}`;

  const stepTitle = STEP_LABELS[currentStep];

  useEffect(() => {
    try {
      const saved = sessionStorage.getItem(sessionKey);
      if (!saved) {
        return;
      }
      const parsed = JSON.parse(saved) as {
        step?: number;
        formData?: ManualIntegrationCreate;
      };
      if (typeof parsed.step === "number" && parsed.step >= 0 && parsed.step < STEP_LABELS.length) {
        setCurrentStep(parsed.step);
      }
      if (parsed.formData) {
        setForm({
          ...INITIAL_FORM,
          ...parsed.formData,
        });
      }
    } catch (error) {}
  }, [sessionKey]);

  useEffect(() => {
    try {
      sessionStorage.setItem(
        sessionKey,
        JSON.stringify({
          step: currentStep,
          formData: form,
        }),
      );
    } catch (error) {}
  }, [currentStep, form, sessionKey]);

  useEffect(() => {
    const hasData =
      Boolean(form.interface_name?.trim()) ||
      Boolean(form.source_system?.trim()) ||
      Boolean(form.destination_system?.trim());

    if (!hasData) {
      return;
    }

    const handleBeforeUnload = (event: BeforeUnloadEvent): void => {
      event.preventDefault();
      event.returnValue = "";
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [form]);

  useEffect(() => {
    const shouldCheck =
      currentStep >= 2 &&
      form.source_system.trim() !== "" &&
      form.destination_system.trim() !== "" &&
      form.business_process.trim() !== "";

    if (!shouldCheck) {
      setDuplicates([]);
      setDuplicateLoading(false);
      return;
    }

    let cancelled = false;
    setDuplicateLoading(true);

    void api
      .checkDuplicates(projectId, {
        source_system: form.source_system,
        destination_system: form.destination_system,
        business_process: form.business_process,
      })
      .then((response) => {
        if (!cancelled) {
          setDuplicates(response);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setDuplicates([]);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDuplicateLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [
    currentStep,
    form.business_process,
    form.destination_system,
    form.source_system,
    projectId,
  ]);

  const stepContent = useMemo(() => {
    const commonProps: CaptureStepProps = {
      projectId,
      form,
      updateField,
      patterns,
      toolOptions,
      frequencyOptions,
      triggerTypeOptions,
      complexityOptions,
    };

    switch (currentStep) {
      case 0:
        return <CaptureStepIdentity {...commonProps} />;
      case 1:
        return <CaptureStepSource {...commonProps} />;
      case 2:
        return (
          <CaptureStepDestination
            {...commonProps}
            duplicates={duplicates}
            duplicateLoading={duplicateLoading}
          />
        );
      case 3:
        return <CaptureStepTechnical {...commonProps} />;
      default:
        return <CaptureStepReview {...commonProps} duplicates={duplicates} />;
    }
  }, [
    complexityOptions,
    currentStep,
    duplicateLoading,
    duplicates,
    form,
    frequencyOptions,
    patterns,
    projectId,
    toolOptions,
    triggerTypeOptions,
  ]);

  function updateField<K extends keyof ManualIntegrationCreate>(
    field: K,
    value: ManualIntegrationCreate[K],
  ): void {
    setForm((current) => ({
      ...current,
      [field]: value,
    }));
    setErrors((current) => {
      if (!(field in current)) {
        return current;
      }
      const next = { ...current };
      delete next[field as string];
      return next;
    });
    setNavigationHint("");
  }

  function collectStepErrors(step: number): Record<string, string> {
    const schema = stepSchemas[step];
    const result = schema.safeParse(form);
    if (result.success) {
      return {};
    }

    const nextErrors: Record<string, string> = {};
    for (const issue of result.error.issues) {
      const path = issue.path[0];
      if (typeof path === "string") {
        nextErrors[path] = issue.message;
      }
    }
    return nextErrors;
  }

  function validateStep(): boolean {
    const nextErrors = collectStepErrors(currentStep);
    if (Object.keys(nextErrors).length === 0) {
      setErrors({});
      return true;
    }
    setErrors(nextErrors);
    return false;
  }

  function navigateToStep(index: number): void {
    if (index <= currentStep) {
      setNavigationHint("");
      setCurrentStep(index);
      return;
    }
    const nextErrors = collectStepErrors(currentStep);
    setErrors(nextErrors);
    setNavigationHint(
      Object.keys(nextErrors).length > 0
        ? `Complete the current step first. ${Object.values(nextErrors)[0]}`
        : "Use Next to validate the current step before moving forward.",
    );
  }

  async function handleSubmit(): Promise<void> {
    setSubmitting(true);
    setSubmitError("");
    try {
      const created = await api.createIntegration(projectId, cleanForm(form));
      sessionStorage.removeItem(sessionKey);
      setCreatedIntegration(created);
      startTransition(() => {
        router.refresh();
      });
    } catch (caughtError) {
      setSubmitError(caughtError instanceof Error ? caughtError.message : "Unable to create integration.");
    } finally {
      setSubmitting(false);
    }
  }

  function resetWizard(): void {
    sessionStorage.removeItem(sessionKey);
    setForm(INITIAL_FORM);
    setCurrentStep(0);
    setErrors({});
    setDuplicates([]);
    setDuplicateLoading(false);
    setSubmitError("");
    setSubmitting(false);
    setCreatedIntegration(null);
  }

  if (createdIntegration) {
    return (
      <section className="app-card border-emerald-200 p-8 dark:border-emerald-900">
        <p className="app-kicker text-emerald-700 dark:text-emerald-300">Capture Complete</p>
        <h2 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--color-text-primary)]">
          Integration captured — {createdIntegration.interface_name ?? createdIntegration.id}
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-[var(--color-text-secondary)]">
          The integration now exists in the catalog with an immutable lineage row and a manual capture audit event.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link href={`/projects/${projectId}/catalog/${createdIntegration.id}`} className="app-button-primary">
            View in Catalog
          </Link>
          <button
            type="button"
            onClick={resetWizard}
            className="app-button-secondary"
          >
            Capture Another
          </button>
        </div>
      </section>
    );
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[16rem_minmax(0,1fr)]">
      <aside className="app-card hidden self-start p-4 xl:block">
        <p className="app-label">Steps</p>
        <div className="mt-4 space-y-1">
          {STEP_LABELS.map((label, index) => {
            const isCurrent = index === currentStep;
            const isCompleted = index < currentStep;
            return (
              <button
                key={label}
                type="button"
                onClick={() => navigateToStep(index)}
                aria-disabled={index > currentStep}
                className={[
                  "flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition",
                  isCurrent
                    ? "bg-[var(--color-accent)]/10 text-[var(--color-accent)]"
                    : isCompleted
                      ? "text-[var(--color-status-active-text)] hover:bg-[var(--color-surface-2)]"
                      : "text-[var(--color-text-secondary)] hover:bg-[var(--color-surface-2)]",
                  index > currentStep ? "cursor-not-allowed opacity-60" : "",
                ].join(" ")}
              >
                <span
                  className={[
                    "flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold",
                    isCurrent
                      ? "bg-[var(--color-accent)] text-white"
                      : isCompleted
                        ? "bg-[var(--color-status-active-text)] text-white"
                        : "bg-[var(--color-surface-3)] text-[var(--color-text-muted)]",
                  ].join(" ")}
                >
                  {isCompleted ? <Check className="h-3.5 w-3.5" /> : index + 1}
                </span>
                <span>
                  <span className="block text-sm font-semibold">{label}</span>
                  <span className="mt-0.5 block text-xs text-[var(--color-text-muted)]">
                    {STEP_DESCRIPTIONS[index]}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
        <div className="mt-5 rounded-lg border border-[var(--color-border)] bg-[var(--color-surface-2)] p-3">
          <p className="text-xs font-semibold text-[var(--color-accent)]">Capture tip</p>
          <p className="mt-1 text-xs leading-5 text-[var(--color-text-secondary)]">
            Complete source and destination first so duplicate checks and pattern suggestions stay meaningful.
          </p>
        </div>
      </aside>

      <div className="space-y-5">
      <section className="app-card p-6 xl:hidden">
        <div className="grid gap-5 xl:grid-cols-[minmax(14rem,0.32fr)_minmax(0,1fr)] xl:items-center">
          <div className="min-w-0">
            <p className="app-label">Step {currentStep + 1} of 5</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--color-text-primary)]">{stepTitle}</h2>
          </div>
          <div className="grid w-full gap-2 sm:grid-cols-5">
            {STEP_LABELS.map((label, index) => {
              const isCurrent = index === currentStep;
              const isCompleted = index < currentStep;
              return (
                <div key={label} className="relative min-w-0">
                  <button
                    type="button"
                    onClick={() => navigateToStep(index)}
                    aria-disabled={index > currentStep}
                    className={[
                      "flex h-full min-h-14 w-full min-w-0 items-center gap-2.5 rounded-2xl border px-3 py-3 text-left text-xs font-semibold uppercase tracking-[0.16em] transition",
                      isCurrent
                        ? "border-[var(--color-accent)] bg-[var(--color-surface)] text-[var(--color-accent)] shadow-[0_0_0_1px_var(--color-accent)]"
                        : isCompleted
                          ? "border-[var(--color-status-active-border)] bg-[var(--color-status-active-bg)] text-[var(--color-status-active-text)]"
                          : "border-[var(--color-border)] bg-[var(--color-surface-3)] text-[var(--color-text-muted)] opacity-75",
                      index > currentStep ? "cursor-not-allowed" : "",
                    ].join(" ")}
                  >
                    <span
                      className={[
                        "inline-flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold",
                        isCurrent
                          ? "bg-[var(--color-accent)]/15 text-[var(--color-accent)]"
                          : isCompleted
                            ? "bg-[var(--color-status-active-text)]/15 text-[var(--color-status-active-text)]"
                            : "bg-[var(--color-surface)] text-[var(--color-text-muted)]",
                      ].join(" ")}
                    >
                      {isCompleted ? <Check className="h-4 w-4" /> : index + 1}
                    </span>
                    <span className="min-w-0 truncate leading-none">{label}</span>
                    </button>
                    {index < STEP_LABELS.length - 1 ? (
                    <span
                      className={[
                        "pointer-events-none absolute left-full top-1/2 hidden h-px w-2 -translate-y-1/2 sm:block",
                        isCompleted ? "bg-[var(--color-status-active-border)]" : "bg-[var(--color-border)]",
                      ].join(" ")}
                    />
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <p className="text-sm text-[var(--color-text-secondary)]">
        Completed steps stay clickable for review. Future steps unlock through <span className="font-semibold text-[var(--color-text-primary)]">Next</span> so validation stays consistent.
      </p>

      {navigationHint ? (
        <section className="rounded-[1.5rem] border border-amber-300 bg-amber-50 p-5 dark:border-amber-900 dark:bg-amber-950/30">
          <p className="text-xs uppercase tracking-[0.25em] text-amber-700 dark:text-amber-300">Step Navigation</p>
          <p className="mt-3 text-sm leading-6 text-amber-900 dark:text-amber-200">{navigationHint}</p>
        </section>
      ) : null}

      {Object.keys(errors).length > 0 ? (
        <section className="rounded-[1.5rem] border border-rose-200 bg-rose-50 p-5">
          <p className="text-xs uppercase tracking-[0.25em] text-rose-700">Validation</p>
          <ul className="mt-3 space-y-2 text-sm text-rose-900">
            {Object.values(errors).map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {duplicates.length > 0 && currentStep >= 3 ? (
        <section className="rounded-[1.5rem] border border-amber-300 bg-amber-50 p-5 dark:border-amber-900 dark:bg-amber-950/30">
          <p className="text-xs uppercase tracking-[0.25em] text-amber-700 dark:text-amber-300">Duplicate Watch</p>
          <p className="mt-3 text-sm leading-6 text-amber-900 dark:text-amber-200">
            {duplicates.length} potential duplicate{duplicates.length === 1 ? "" : "s"} matched this route. You can continue, but this should be intentional.
          </p>
        </section>
      ) : null}

      <section className="app-card p-6">
        {stepContent}
      </section>

      {submitError ? <p className="text-sm text-rose-600">{submitError}</p> : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => {
            setNavigationHint("");
            setCurrentStep((current) => Math.max(0, current - 1));
          }}
          disabled={currentStep === 0 || submitting}
          className="app-button-secondary disabled:cursor-not-allowed disabled:opacity-40"
        >
          Back
        </button>
        <div className="flex flex-wrap gap-3">
          {currentStep < STEP_LABELS.length - 1 ? (
            <button
              type="button"
              onClick={() => {
                if (validateStep()) {
                  setNavigationHint("");
                  setCurrentStep((current) => Math.min(STEP_LABELS.length - 1, current + 1));
                } else {
                  const nextErrors = collectStepErrors(currentStep);
                  setNavigationHint(
                    Object.values(nextErrors)[0] ?? "Resolve the current step validation issues before moving forward.",
                  );
                }
              }}
              className="app-button-primary"
            >
              Next
            </button>
          ) : (
            <button
              type="button"
              onClick={() => {
                if (validateStep()) {
                  setNavigationHint("");
                  void handleSubmit();
                } else {
                  const nextErrors = collectStepErrors(currentStep);
                  setNavigationHint(
                    Object.values(nextErrors)[0] ?? "Resolve the current step validation issues before submitting.",
                  );
                }
              }}
              disabled={submitting}
              className="app-button-primary disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? "Creating…" : "Create Integration"}
            </button>
          )}
        </div>
      </div>
      </div>
    </div>
  );
}
