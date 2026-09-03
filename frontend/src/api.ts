/** PayTrace API client.
 *  All requests go through Vite's dev proxy to http://127.0.0.1:8000.
 *  No secrets, no credentials, no sensitive data.
 */

import type {
  ReconciliationSummary,
  PaginatedResults,
  GroupDetail,
} from "./types";

const BASE = "/api/v1/reconciliation";

export async function fetchSummary(): Promise<ReconciliationSummary> {
  const res = await fetch(`${BASE}/summary`);
  if (!res.ok) throw new Error(`Summary fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchResults(params?: {
  status?: string;
  exception_type?: string;
  human_review?: boolean;
}): Promise<PaginatedResults> {
  const query = new URLSearchParams();
  if (params?.status) query.set("status", params.status);
  if (params?.exception_type) query.set("exception_type", params.exception_type);
  if (params?.human_review !== undefined)
    query.set("human_review", String(params.human_review));

  const qs = query.toString();
  const url = qs ? `${BASE}/results?${qs}` : `${BASE}/results`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`Results fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchGroupDetail(
  groupId: string,
): Promise<GroupDetail> {
  const res = await fetch(`${BASE}/results/${groupId}`);
  if (!res.ok) throw new Error(`Detail fetch failed: ${res.status}`);
  return res.json();
}

import type { InvestigationResult } from "./types";

export async function fetchInvestigation(groupId: string): Promise<InvestigationResult> {
  const res = await fetch(`${BASE}/results/${groupId}/investigate`);
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `Investigation failed: ${res.status}`);
  }
  return res.json();
}
