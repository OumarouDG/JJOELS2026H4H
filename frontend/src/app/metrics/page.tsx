"use client";

import { useEffect, useState } from "react";
import { getMetrics, API_BASE } from "@/lib/api";
import type { Metrics } from "@/lib/types";

export default function MetricsPage() {
  const [m, setM] = useState<Metrics | null>(null);

  useEffect(() => {
    getMetrics().then(setM);
  }, []);

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-bold">Model Metrics</h1>

      {!m ? (
        <div className="text-sm text-gray-500">Loading...</div>
      ) : (
        <>
          <div className="rounded-lg border p-4">
            <div className="font-semibold">Accuracy</div>
            <div className="text-xl">
              {Math.round(m.accuracy * 100)}%
            </div>
          </div>

          <div className="rounded-lg border p-4">
            <div className="mb-2 font-semibold">Labels</div>
            <div className="text-sm text-gray-700">
              {m.labels.join(", ")}
            </div>
          </div>

          <div className="rounded-lg border p-4">
            <div className="mb-2 font-semibold">Feature Names</div>
            {m.feature_names.length ? (
              <ul className="list-inside list-disc text-sm">
                {m.feature_names.map((f) => (
                  <li key={f} className="font-mono text-xs">
                    {f}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="text-sm text-gray-500">
                No feature list available yet.
              </div>
            )}
          </div>

          {m.confusion_matrix_url && (
            <div className="rounded-lg border p-4">
              <div className="mb-2 font-semibold">Confusion Matrix</div>
              <img
                src={
                  m.confusion_matrix_url.startsWith("http")
                    ? m.confusion_matrix_url
                    : `${API_BASE}${m.confusion_matrix_url}`
                }
                alt="confusion matrix"
                className="max-w-full rounded border"
              />
            </div>
          )}
        </>
      )}
    </main>
  );
}