"use client";

import CaptureTimeline from "@/components/CaptureTimeline";

export const dynamic = "force-dynamic"; 

export default function HistoryPage() {
  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <h1 className="text-2xl font-bold">Capture History</h1>
      <CaptureTimeline refreshMs={4000} />
    </main>
  );
}