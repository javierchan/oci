/* Route guard for project-scoped pages. */

import type { ReactNode } from "react";
import { notFound } from "next/navigation";

import { api, isApiErrorStatus } from "@/lib/api";

type ProjectLayoutProps = {
  children: ReactNode;
  params: {
    projectId: string;
  };
};

export default async function ProjectLayout({
  children,
  params,
}: ProjectLayoutProps): Promise<JSX.Element> {
  try {
    await api.getProject(params.projectId);
  } catch (error: unknown) {
    if (isApiErrorStatus(error, 404, "/api/v1/projects/")) {
      notFound();
    }
    throw error;
  }

  return <>{children}</>;
}
