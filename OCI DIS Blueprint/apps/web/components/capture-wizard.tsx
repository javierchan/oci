"use client";

/* Five-step guided manual capture flow with validation, duplicate checks, and submit handling. */

import Link from "next/link";
import { useRouter } from "next/navigation";
import { startTransition, useEffect, useMemo, useState } from "react";
import { z } from "zod";

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
  updateField: <K extends keyof ManualIntegrationCreate>(field: K, value: ManualIntegrationCreate[K]) => void;
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
  }

  function validateStep(): boolean {
    const schema = stepSchemas[currentStep];
    const result = schema.safeParse(form);
    if (result.success) {
      setErrors({});
      return true;
    }

    const nextErrors: Record<string, string> = {};
    for (const issue of result.error.issues) {
      const path = issue.path[0];
      if (typeof path === "string") {
        nextErrors[path] = issue.message;
      }
    }
    setErrors(nextErrors);
    return false;
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
      <section className="rounded-[2rem] border border-emerald-200 bg-white p-8 shadow-sm">
        <p className="text-xs uppercase tracking-[0.25em] text-emerald-700">Capture Complete</p>
        <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">
          Integration captured — {createdIntegration.interface_name ?? createdIntegration.id}
        </h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-600">
          The integration now exists in the catalog with a synthetic lineage row and a manual capture audit event.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href={`/projects/${projectId}/catalog/${createdIntegration.id}`}
            className="inline-flex items-center justify-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
          >
            View in Catalog
          </Link>
          <button
            type="button"
            onClick={resetWizard}
            className="inline-flex items-center justify-center rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:text-slate-950"
          >
            Capture Another
          </button>
        </div>
      </section>
    );
  }

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.25em] text-slate-500">Step {currentStep + 1} of 5</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-950">{stepTitle}</h2>
          </div>
          <div className="grid w-full gap-3 md:grid-cols-5 lg:max-w-3xl">
            {STEP_LABELS.map((label, index) => (
              <button
                key={label}
                type="button"
                onClick={() => {
                  if (index <= currentStep) {
                    setCurrentStep(index);
                  }
                }}
                className={[
                  "rounded-2xl border px-3 py-3 text-left text-xs font-semibold uppercase tracking-[0.2em] transition",
                  index === currentStep
                    ? "border-sky-400 bg-sky-50 text-sky-700"
                    : index < currentStep
                      ? "border-emerald-300 bg-emerald-50 text-emerald-700"
                      : "border-slate-200 bg-slate-50 text-slate-500",
                ].join(" ")}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </section>

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
        <section className="rounded-[1.5rem] border border-amber-300 bg-amber-50 p-5">
          <p className="text-xs uppercase tracking-[0.25em] text-amber-700">Duplicate Watch</p>
          <p className="mt-3 text-sm leading-6 text-amber-900">
            {duplicates.length} potential duplicate{duplicates.length === 1 ? "" : "s"} matched this route. You can continue, but this should be intentional.
          </p>
        </section>
      ) : null}

      <section className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
        {stepContent}
      </section>

      {submitError ? <p className="text-sm text-rose-600">{submitError}</p> : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          type="button"
          onClick={() => setCurrentStep((current) => Math.max(0, current - 1))}
          disabled={currentStep === 0 || submitting}
          className="inline-flex items-center justify-center rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:border-slate-400 hover:text-slate-950 disabled:cursor-not-allowed disabled:opacity-40"
        >
          Back
        </button>
        <div className="flex flex-wrap gap-3">
          {currentStep < STEP_LABELS.length - 1 ? (
            <button
              type="button"
              onClick={() => {
                if (validateStep()) {
                  setCurrentStep((current) => Math.min(STEP_LABELS.length - 1, current + 1));
                }
              }}
              className="inline-flex items-center justify-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
            >
              Next
            </button>
          ) : (
            <button
              type="button"
              onClick={() => {
                if (validateStep()) {
                  void handleSubmit();
                }
              }}
              disabled={submitting}
              className="inline-flex items-center justify-center rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
            >
              {submitting ? "Creating…" : "Create Integration"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
