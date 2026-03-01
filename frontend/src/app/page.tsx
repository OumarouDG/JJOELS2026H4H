"use client";

import { useState } from "react";
import StatusBanner from "@/components/StatusBanner";
import CaptureButton from "@/components/CaptureButton";
import type { CaptureResult } from "@/lib/types";


export default function HomePage() {
  const [result, setResult] = useState<CaptureResult | null>(null);

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-bold">JJOELS2026H4H Demo</h1>

      <StatusBanner />

      <div className="rounded-lg border p-4">
        <CaptureButton onResult={setResult} />
      </div>

      <div className="rounded-lg border p-4">
        <div className="font-semibold">Last Result</div>
        <pre className="mt-2 text-xs">
          {result ? JSON.stringify(result, null, 2) : "No capture yet."}
        </pre>
      </div>
    </main>
  );
}