"use client";

import { useState } from "react";
import type { CaptureResult } from "@/lib/types";

type Props = {
  onResult?: (r: CaptureResult) => void;
};

export default function CaptureButton({ onResult }: Props) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleClick() {
    setErr(null);
    setLoading(true);

    try {
      // NEW: call FastAPI /record endpoint
      const res = await fetch(
        "http://localhost:8000/record?seconds=5",
        { method: "POST" }
      );

      if (!res.ok) {
        throw new Error("Recording failed");
      }

      const data = await res.json();

      // optional callback
      onResult?.(data);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Capture failed";
      setErr(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={handleClick}
        disabled={loading}
        className="rounded-lg border px-4 py-2 font-medium hover:bg-gray-100 disabled:opacity-60"
      >
        {loading ? "Recording..." : "Record 5s"}
      </button>

      {err && <div className="text-sm text-red-600">{err}</div>}
    </div>
  );
}