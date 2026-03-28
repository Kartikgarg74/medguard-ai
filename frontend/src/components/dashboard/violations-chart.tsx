"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";

interface ViolationsChartProps {
  labels: string[];
  total: number[];
  violations: number[];
}

export default function ViolationsChart({
  labels,
  total,
  violations,
}: ViolationsChartProps) {
  const data = labels.map((label, i) => ({
    platform: label,
    total: total[i],
    violations: violations[i],
    compliant: total[i] - violations[i],
  }));

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-sm font-semibold text-gray-600 mb-4">
        Violations by Platform
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="platform" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="compliant" fill="#16a34a" name="Compliant" />
          <Bar dataKey="violations" fill="#dc2626" name="Violations" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
