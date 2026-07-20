import { redirect } from "next/navigation";

type LegacyGraphPageProps = {
  params: Promise<{
    projectId: string;
  }>;
};

export default async function LegacyGraphPage({ params }: LegacyGraphPageProps): Promise<never> {
  const { projectId } = await params;
  redirect(`/projects/${projectId}/map`);
}
