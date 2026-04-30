/* Shared helpers for graceful project-scoped routing failures. */

import { isApiErrorCode } from "@/lib/api";

export function projectRootHref(projectId: string): string {
  return `/projects/${projectId}`;
}

export function isProjectNotFoundError(error: unknown): boolean {
  return isApiErrorCode(error, "PROJECT_NOT_FOUND");
}
