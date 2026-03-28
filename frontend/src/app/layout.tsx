import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MedGuard AI",
  description: "Medicine Price Compliance System under DPCO 2013",
};

const navItems = [
  { href: "/", label: "Dashboard" },
  { href: "/violations", label: "Violations" },
  { href: "/medicines", label: "Medicines" },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="min-h-screen flex">
          {/* Sidebar */}
          <aside className="w-56 bg-slate-900 text-white flex flex-col">
            <div className="p-5 border-b border-slate-700">
              <h1 className="text-lg font-bold tracking-tight">
                MedGuard AI
              </h1>
              <p className="text-xs text-slate-400 mt-1">DPCO Compliance</p>
            </div>
            <nav className="flex-1 p-3 space-y-1">
              {navItems.map((item) => (
                <a
                  key={item.href}
                  href={item.href}
                  className="block px-3 py-2 rounded-lg text-sm text-slate-300 hover:bg-slate-800 hover:text-white transition-colors"
                >
                  {item.label}
                </a>
              ))}
            </nav>
            <div className="p-4 border-t border-slate-700 text-xs text-slate-500">
              ET AI Hackathon 2026
            </div>
          </aside>

          {/* Main content */}
          <main className="flex-1 p-8 overflow-auto">{children}</main>
        </div>
      </body>
    </html>
  );
}
