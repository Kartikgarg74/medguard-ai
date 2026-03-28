const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function fetchAPI<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export interface DashboardStats {
  medicines_in_catalog: number;
  dpco_scheduled: number;
  total_checks: number;
  violations: number;
  compliance_rate: number;
  platforms_monitored: number;
}

export interface Violation {
  id: string;
  medicine_name: string;
  platform: string;
  ceiling_price: number;
  retail_price: number;
  overcharge_amount: number;
  overcharge_pct: number;
  status: string;
  severity: string;
  dpco_rule: string;
  reasoning: string;
  confidence: number;
  checked_by: string;
  checked_at: string;
}

export interface ViolationStats {
  total_checked: number;
  total_violations: number;
  compliance_rate: number;
  total_overcharge: number;
  by_severity: Record<string, number>;
  by_platform: Record<string, number>;
}

export interface PlatformChart {
  labels: string[];
  total: number[];
  violations: number[];
}

export interface TopViolator {
  medicine_name: string;
  platform: string;
  overcharge_pct: number;
  overcharge_amount: number;
  severity: string;
}

export const api = {
  getDashboardStats: () => fetchAPI<DashboardStats>("/api/dashboard/stats"),
  getViolationStats: () => fetchAPI<ViolationStats>("/api/violations/stats"),
  getViolationsByPlatform: () =>
    fetchAPI<PlatformChart>("/api/dashboard/violations-by-platform"),
  getTopViolators: () => fetchAPI<TopViolator[]>("/api/dashboard/top-violators"),
  getViolations: (page = 1, severity = "") =>
    fetchAPI<{ total: number; results: Violation[] }>(
      `/api/violations?page=${page}&limit=20${severity ? `&severity=${severity}` : ""}`
    ),
  searchMedicines: (query: string) =>
    fetchAPI<{ total: number; results: any[] }>(
      `/api/medicines?search=${encodeURIComponent(query)}&limit=20`
    ),
  getMedicine: (id: string) => fetchAPI<any>(`/api/medicines/${id}`),
  getAuditVerify: () => fetchAPI<{ valid: boolean; total_entries: number }>(
    "/api/audit/verify"
  ),
  getPipelineStatus: () => fetchAPI<any>("/api/scraper/status"),
  triggerScan: () =>
    fetch(`${API_BASE}/api/scraper/trigger`, { method: "POST" }).then((r) =>
      r.json()
    ),
};
