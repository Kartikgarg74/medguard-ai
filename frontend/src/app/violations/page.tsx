"use client";

import { useEffect, useState } from "react";
import { api, Violation } from "@/lib/api";

const severityBadge: Record<string, string> = {
  critical: "bg-red-100 text-red-800",
  high: "bg-orange-100 text-orange-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-green-100 text-green-800",
};

export default function ViolationsPage() {
  const [violations, setViolations] = useState<Violation[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const data = await api.getViolations(page, filter);
        setViolations(data.results);
        setTotal(data.total);
      } catch {
        /* ignore */
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [page, filter]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Violations</h2>
          <p className="text-sm text-gray-500">{total} violations found</p>
        </div>
        <select
          value={filter}
          onChange={(e) => {
            setFilter(e.target.value);
            setPage(1);
          }}
          className="border rounded-lg px-3 py-2 text-sm"
        >
          <option value="">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="px-4 py-3 text-left font-medium text-gray-600">
                Medicine
              </th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">
                Platform
              </th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">
                MRP (Rs)
              </th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">
                Ceiling (Rs)
              </th>
              <th className="px-4 py-3 text-right font-medium text-gray-600">
                Overcharge
              </th>
              <th className="px-4 py-3 text-center font-medium text-gray-600">
                Severity
              </th>
              <th className="px-4 py-3 text-left font-medium text-gray-600">
                DPCO Rule
              </th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  Loading...
                </td>
              </tr>
            ) : violations.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-gray-400">
                  No violations found
                </td>
              </tr>
            ) : (
              violations.map((v) => (
                <tr key={v.id} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium">{v.medicine_name}</td>
                  <td className="px-4 py-3">{v.platform}</td>
                  <td className="px-4 py-3 text-right">
                    {v.retail_price?.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {v.ceiling_price?.toFixed(2) || "N/A"}
                  </td>
                  <td className="px-4 py-3 text-right text-red-600 font-semibold">
                    Rs {v.overcharge_amount?.toFixed(2)} (
                    {v.overcharge_pct?.toFixed(1)}%)
                  </td>
                  <td className="px-4 py-3 text-center">
                    <span
                      className={`text-xs px-2 py-1 rounded-full font-medium ${
                        severityBadge[v.severity] || severityBadge.low
                      }`}
                    >
                      {v.severity?.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500">
                    {v.dpco_rule}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 20 && (
        <div className="flex justify-center gap-2">
          <button
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
            className="px-3 py-1 border rounded text-sm disabled:opacity-30"
          >
            Previous
          </button>
          <span className="px-3 py-1 text-sm text-gray-500">
            Page {page} of {Math.ceil(total / 20)}
          </span>
          <button
            disabled={page >= Math.ceil(total / 20)}
            onClick={() => setPage(page + 1)}
            className="px-3 py-1 border rounded text-sm disabled:opacity-30"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
