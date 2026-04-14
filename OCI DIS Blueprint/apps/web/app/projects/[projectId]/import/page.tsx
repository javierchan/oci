/* Server-rendered import page with client upload flow. */

import { ImportUpload } from "@/components/import-upload";
import { api } from "@/lib/api";

type ProjectImportPageProps = {
  params: {
    projectId: string;
  };
};

export default async function ProjectImportPage({
  params,
}: ProjectImportPageProps): Promise<JSX.Element> {
  const imports = await api.listImports(params.projectId);
  return <ImportUpload projectId={params.projectId} initialBatches={imports.batches} />;
}
