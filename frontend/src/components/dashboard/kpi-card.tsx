"use client";

interface KPICardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  color?: "blue" | "red" | "green" | "orange" | "purple";
}

const colorMap = {
  blue: "bg-blue-50 text-blue-700 border-blue-200",
  red: "bg-red-50 text-red-700 border-red-200",
  green: "bg-green-50 text-green-700 border-green-200",
  orange: "bg-orange-50 text-orange-700 border-orange-200",
  purple: "bg-purple-50 text-purple-700 border-purple-200",
};

export default function KPICard({
  title,
  value,
  subtitle,
  color = "blue",
}: KPICardProps) {
  return (
    <div
      className={`rounded-xl border p-6 text-center ${colorMap[color]}`}
    >
      <div className="text-3xl font-bold">{value}</div>
      <div className="text-xs uppercase tracking-wider mt-1 opacity-70">
        {title}
      </div>
      {subtitle && (
        <div className="text-xs mt-2 opacity-50">{subtitle}</div>
      )}
    </div>
  );
}
