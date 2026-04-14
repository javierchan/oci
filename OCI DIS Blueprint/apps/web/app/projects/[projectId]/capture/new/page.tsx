/* Guided manual capture page that bootstraps the five-step wizard. */

import { Breadcrumb } from "@/components/breadcrumb";
import { CaptureWizard } from "@/components/capture-wizard";
import { api } from "@/lib/api";

type CaptureNewPageProps = {
  params: {
    projectId: string;
  };
};

export default async function CaptureNewPage({
  params,
}: CaptureNewPageProps): Promise<JSX.Element> {
  const [project, patterns, tools, frequencies, triggerTypes, complexities] = await Promise.all([
    api.getProject(params.projectId),
    api.listPatterns(),
    api.listDictionaryOptions("TOOLS"),
    api.listDictionaryOptions("FREQUENCY"),
    api.listDictionaryOptions("TRIGGER_TYPE"),
    api.listDictionaryOptions("COMPLEXITY"),
  ]);

  return (
    <div className="space-y-8">
      <section className="app-card p-6">
        <p className="app-kicker">Capture Wizard</p>
        <h1 className="mt-2 text-4xl font-semibold tracking-tight text-[var(--color-text-primary)]">
          New Integration for {project.name}
        </h1>
        <p className="mt-3 max-w-3xl text-sm leading-6 text-[var(--color-text-secondary)]">
          Move through identity, source, destination, technical sizing, and final review before the integration is added to the catalog.
        </p>
        <div className="mt-4">
          <Breadcrumb
            items={[
              { label: "Home", href: "/projects" },
              { label: "Projects", href: "/projects" },
              { label: project.name, href: `/projects/${params.projectId}` },
              { label: "Capture", href: `/projects/${params.projectId}/capture` },
              { label: "New" },
            ]}
          />
        </div>
      </section>

      <CaptureWizard
        projectId={params.projectId}
        patterns={patterns.patterns}
        toolOptions={tools.options}
        frequencyOptions={frequencies.options}
        triggerTypeOptions={triggerTypes.options}
        complexityOptions={complexities.options}
      />
    </div>
  );
}
