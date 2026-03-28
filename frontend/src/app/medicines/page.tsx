"use client";

import { useState } from "react";
import { api } from "@/lib/api";

export default function MedicinesPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<any[]>([]);
  const [selected, setSelected] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  async function handleSearch() {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const data = await api.searchMedicines(query);
      setResults(data.results);
      setSelected(null);
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  async function handleSelect(id: string) {
    try {
      const detail = await api.getMedicine(id);
      setSelected(detail);
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Medicine Lookup</h2>
        <p className="text-sm text-gray-500">
          Search and compare prices across platforms
        </p>
      </div>

      {/* Search Bar */}
      <div className="flex gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Search by medicine name, salt, or brand..."
          className="flex-1 border rounded-lg px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <button
          onClick={handleSearch}
          disabled={loading}
          className="bg-blue-600 text-white px-6 py-2 rounded-lg text-sm hover:bg-blue-700 transition disabled:opacity-50"
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </div>

      {/* Results List */}
      {results.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 divide-y">
          {results.map((med) => (
            <div
              key={med.id}
              onClick={() => handleSelect(med.id)}
              className="px-4 py-3 hover:bg-blue-50 cursor-pointer flex justify-between items-center"
            >
              <div>
                <div className="text-sm font-medium">{med.name}</div>
                <div className="text-xs text-gray-400">
                  {med.salt_composition} | {med.manufacturer}
                </div>
              </div>
              <div className="flex items-center gap-2">
                {med.dpco_scheduled && (
                  <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">
                    DPCO
                  </span>
                )}
                {med.nlem_listed && (
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                    NLEM
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Price Comparison Detail */}
      {selected && (
        <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-4">
          <div>
            <h3 className="text-lg font-bold">{selected.name}</h3>
            <p className="text-sm text-gray-500">
              {selected.salt_composition} | {selected.formulation}{" "}
              {selected.dosage}
            </p>
          </div>

          {selected.ceiling_price && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="text-xs text-blue-600 uppercase font-medium">
                NPPA Ceiling Price
              </div>
              <div className="text-2xl font-bold text-blue-700">
                Rs {selected.ceiling_price.price?.toFixed(2)}
              </div>
              {selected.ceiling_price.notification && (
                <div className="text-xs text-blue-400 mt-1">
                  SO: {selected.ceiling_price.notification}
                </div>
              )}
            </div>
          )}

          {Object.keys(selected.price_comparison || {}).length > 0 && (
            <div>
              <h4 className="text-sm font-semibold text-gray-600 mb-3">
                Platform Price Comparison
              </h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {Object.entries(selected.price_comparison).map(
                  ([platform, data]: [string, any]) => (
                    <div
                      key={platform}
                      className="border rounded-lg p-4 text-center"
                    >
                      <div className="text-xs text-gray-400 uppercase">
                        {platform}
                      </div>
                      <div className="text-xl font-bold mt-1">
                        Rs {data.selling_price?.toFixed(2)}
                      </div>
                      <div className="text-xs text-gray-400 line-through">
                        MRP Rs {data.listed_price?.toFixed(2)}
                      </div>
                      {data.discount_pct > 0 && (
                        <div className="text-xs text-green-600 font-medium mt-1">
                          {data.discount_pct.toFixed(0)}% off
                        </div>
                      )}
                    </div>
                  )
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
