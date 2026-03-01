"use client";

import { useEffect, useState } from "react";
import StatusBanner from "@/components/StatusBanner";
import CaptureButton from "@/components/CaptureButton";
import LiveGasChart from "@/components/LiveGasChart";
import FeatureTable from "@/components/FeatureTable";
import CaptureTimeline from "@/components/CaptureTimeline";
import type { CaptureResult, SensorSample } from "@/lib/types";

export default function HomePage() {
  const [result, setResult] = useState<CaptureResult | null>(null);

  // Simple mock live stream so chart looks alive during demo.
  // Replace later with real backend stream or collector push.
  const [samples, setSamples] = useState<SensorSample[]>([]);

  useEffect(() => {
    const id = window.setInterval(() => {
      const now = Date.now();
      const last = samples.length ? samples[samples.length - 1].gas_ohms : 80000;
      const next = Math.max(1000, Math.round(last + (Math.random() - 0.5) * 5000));

      setSamples((prev) => {
        const nxt: SensorSample = {
          t: now,
          tempC: 22,
          humidity: 45,
          pressure_hPa: 1013,
          gas_ohms: next,
        };
        const merged = [...prev, nxt];
        return merged.slice(-120); // ~60s if 2Hz
      });
    }, 500);

    return () => window.clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-bold">JJOELS2026H4H Demo</h1>

      <StatusBanner />

      <div className="rounded-lg border p-4">
        <CaptureButton onResult={setResult} />
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <LiveGasChart samples={samples} />
        <FeatureTable features={result?.features} />
      </div>

      <div className="rounded-lg border p-4">
        <div className="font-semibold">Last Result</div>
        <pre className="mt-2 overflow-auto rounded bg-gray-50 p-3 text-xs">
          {result ? JSON.stringify(result, null, 2) : "No capture yet."}
        </pre>
      </div>

      <CaptureTimeline />
    </main>
  );
}