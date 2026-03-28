"use client";

import { useEffect, useState } from "react";
import KPICard from "@/components/dashboard/kpi-card";
import ViolationsChart from "@/components/dashboard/violations-chart";
import TopViolators from "@/components/dashboard/top-violators";
import {
  api,
  DashboardStats,
  PlatformChart,
  TopViolator,
} from "@/lib/api";

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [chart, setChart] = useState<PlatformChart | null>(null);
  const [violators, setViolators] = useState<TopViolator[]>([]);
  const [auditOk, setAuditOk] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadData() {
      try {
        const [s, c, v, a] = await Promise.all([
          api.getDashboardStats(),
          api.getViolationsByPlatform(),
          api.getTopViolators(),
          api.getAuditVerify(),
        ]);
        setStats(s);
        setChart(c);
        setViolators(v);
        setAuditOk(a.valid);
      } catch (e: any) {
        setError(e.message || "Failed to load dashboard data");
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-gray-400">
        Loading dashboard...
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg">
        {error}. Make sure the backend is running on port 8000.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Compliance Dashboard</h2>
          <p className="text-sm text-gray-500">
            DPCO 2013 Medicine Price Monitoring
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`text-xs px-2 py-1 rounded-full ${
              auditOk
                ? "bg-green-100 text-green-700"
                : "bg-red-100 text-red-700"
            }`}
          >
            Audit Chain: {auditOk ? "Valid" : "Broken"}
          </span>
          <button
            onClick={() => api.triggerScan()}
            className="bg-blue-600 text-white text-sm px-4 py-2 rounded-lg hover:bg-blue-700 transition"
          >
            Trigger Scan
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <KPICard
            title="Medicines Monitored"
            value={stats.medicines_in_catalog.toLocaleString()}
            color="blue"
          />
          <KPICard
            title="Violations Found"
            value={stats.violations}
            color="red"
          />
          <KPICard
            title="Compliance Rate"
            value={`${stats.compliance_rate}%`}
            color={stats.compliance_rate >= 90 ? "green" : "orange"}
          />
          <KPICard
            title="Platforms Monitored"
            value={stats.platforms_monitored}
            color="purple"
          />
        </div>
      )}

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {chart && chart.labels.length > 0 && (
          <ViolationsChart
            labels={chart.labels}
            total={chart.total}
            violations={chart.violations}
          />
        )}
        <TopViolators violators={violators} />
      </div>
    </div>
  );
}
