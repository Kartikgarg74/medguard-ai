"use client";

interface TopViolator {
  medicine_name: string;
  platform: string;
  overcharge_pct: number;
  overcharge_amount: number;
  severity: string;
}

const severityBadge: Record<string, string> = {
  critical: "bg-red-100 text-red-800",
  high: "bg-orange-100 text-orange-800",
  medium: "bg-yellow-100 text-yellow-800",
  low: "bg-green-100 text-green-800",
};

export default function TopViolators({
  violators,
}: {
  violators: TopViolator[];
}) {
  if (!violators.length) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6 text-center text-gray-400">
        No violations found
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-sm font-semibold text-gray-600 mb-4">
        Top Violators
      </h3>
      <div className="space-y-3">
        {violators.map((v, i) => (
          <div
            key={i}
            className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0"
          >
            <div className="flex-1">
              <div className="text-sm font-medium">{v.medicine_name}</div>
              <div className="text-xs text-gray-400">{v.platform}</div>
            </div>
            <div className="text-right mr-3">
              <div className="text-sm font-bold text-red-600">
                +{v.overcharge_pct?.toFixed(1)}%
              </div>
              <div className="text-xs text-gray-400">
                Rs {v.overcharge_amount?.toFixed(2)}
              </div>
            </div>
            <span
              className={`text-xs px-2 py-1 rounded-full font-medium ${severityBadge[v.severity] || severityBadge.low}`}
            >
              {v.severity?.toUpperCase()}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
