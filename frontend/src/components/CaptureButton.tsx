"use client";

import { useState } from "react";
import { postRecord } from "@/lib/api";
import type { CaptureResult } from "@/lib/types";

type Props = {
  onResult: (r: CaptureResult) => void;
  onCaptureState?: (capturing: boolean) => void;
};

export default function CaptureButton({ onResult, onCaptureState }: Props) {
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function handleClick() {
    setErr(null);
    setLoading(true);
    onCaptureState?.(true);

    try {
      const capture = await postRecord(5000);
      onResult(capture);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Record failed";
      setErr(msg);
    } finally {
      onCaptureState?.(false);
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={handleClick}
        disabled={loading}
        className="rounded-lg border px-4 py-2 font-medium bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-60"
      >
        {loading ? "Capturing..." : "Capture 5s"}
      </button>

      {err && <div className="text-sm text-red-600">{err}</div>}
    </div>
  );
}