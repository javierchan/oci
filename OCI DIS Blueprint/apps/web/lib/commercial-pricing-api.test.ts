/* Contract tests for the Admin Pricing commercial-catalog API client. */

import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "./api";
import type { CommercialWorkspace } from "./types";

const workspace: CommercialWorkspace = {
  document: null,
  summary: { skus: 0, candidates: 0, pending: 0, approved: 0, blocked: 0, exceptions: 0 },
  candidates: [],
  page: 1,
  page_size: 50,
  total: 0,
  exceptions: [],
  exceptions_page: 1,
  exceptions_page_size: 50,
  exceptions_total: 0,
  releases: [],
  field_authority: {},
};

function response(): Response {
  return new Response(JSON.stringify(workspace), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function requestPath(call: unknown[]): string {
  return new URL(String(call[0])).pathname + new URL(String(call[0])).search;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("commercial catalog API client", () => {
  it("loads the typed workspace with server pagination and filters", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response());
    vi.stubGlobal("fetch", fetchMock);

    await api.getCommercialCatalog({ document_id: "doc/1", search: "B95701", status: "pending_review", page: 2, page_size: 50 });

    expect(requestPath(fetchMock.mock.calls[0])).toBe(
      "/api/v1/pricing/commercial-catalog?document_id=doc%2F1&search=B95701&status=pending_review&page=2&page_size=50",
    );
    expect(fetchMock.mock.calls[0]?.[1]?.headers).toEqual(expect.any(Headers));
  });

  it("uploads an XLSX document as multipart evidence", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response());
    vi.stubGlobal("fetch", fetchMock);
    const file = new File(["official evidence"], "oracle-price-list.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });

    await api.importCommercialDocument(file);

    expect(requestPath(fetchMock.mock.calls[0])).toBe("/api/v1/pricing/commercial-documents");
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("POST");
    const body = fetchMock.mock.calls[0]?.[1]?.body;
    expect(body).toBeInstanceOf(FormData);
    expect((body as FormData).get("file")).toBe(file);
    expect((fetchMock.mock.calls[0]?.[1]?.headers as Headers).has("Content-Type")).toBe(false);
  });

  it.each([
    ["approve evidence", () => api.approveCommercialDocument("doc/1"), "/api/v1/pricing/commercial-documents/doc%2F1/approve", undefined],
    ["finalize catalog review", () => api.finalizeCommercialCatalogReview("doc/1", { rationale: "Deterministic fixtures and official evidence establish the disposition." }), "/api/v1/pricing/commercial-documents/doc%2F1/finalize-review", { rationale: "Deterministic fixtures and official evidence establish the disposition." }],
    ["review candidate", () => api.reviewCommercialCandidate("candidate/1", { decision: "approve", rationale: "Verified against the official source." }), "/api/v1/pricing/commercial-candidates/candidate%2F1/review", { decision: "approve", rationale: "Verified against the official source." }],
    ["revalidate candidate", () => api.revalidateCommercialCandidate("candidate/1"), "/api/v1/pricing/commercial-candidates/candidate%2F1/revalidate", undefined],
    ["review exception", () => api.reviewCommercialException("exception/1", { decision: "accept_risk", rationale: "Approved as a documented customer exception." }), "/api/v1/pricing/commercial-exceptions/exception%2F1/review", { decision: "accept_risk", rationale: "Approved as a documented customer exception." }],
    ["promote release", () => api.promoteCommercialRelease("doc/1"), "/api/v1/pricing/commercial-documents/doc%2F1/releases", undefined],
  ])("calls the governed %s endpoint", async (_label, action, expectedPath, expectedBody) => {
    const fetchMock = vi.fn().mockResolvedValue(response());
    vi.stubGlobal("fetch", fetchMock);

    await action();

    expect(requestPath(fetchMock.mock.calls[0])).toBe(expectedPath);
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("POST");
    if (expectedBody) {
      expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual(expectedBody);
    }
  });
});
