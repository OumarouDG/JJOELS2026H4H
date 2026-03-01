"use client";

import { useEffect, useState } from "react";
import { getCaptures } from "@/lib/api";
import type { CaptureResult } from "@/lib/types";

type Props = {
  title?: string;
  refreshMs?: number;
  items?: CaptureResult[];
};

function fmt(ts: string) {
  const d = new Date(ts);
  return d.toLocaleString();
}

export default function CaptureTimeline({
  title = "Capture Timeline",
  refreshMs = 5000,
  items,
}: Props) {
  const [fetched, setFetched] = useState<CaptureResult[]>([]);
  const [loading, setLoading] = useState(items ? false : true);

  useEffect(() => {
    if (items) {
      setLoading(false);
      return;
    }

    let alive = true;

    async function load() {
      try {
        setLoading(true);
        const list = await getCaptures();
        if (!alive) return;
        setFetched(list);
      } finally {
        if (alive) setLoading(false);
      }
    }

    load();
    const id = window.setInterval(load, refreshMs);

    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [items, refreshMs]);

  const rows = items ?? fetched;

  return (
    <div className="rounded-lg border p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="font-semibold">{title}</div>
        <div className="text-xs text-gray-500">
          {loading ? "Loading..." : `${rows.length} items`}
        </div>
      </div>

      {!rows.length ? (
        <div className="text-sm text-gray-500">No captures yet.</div>
      ) : (
        <div className="max-h-80 overflow-auto rounded border">
          <ul className="divide-y">
            {rows
              .slice()
              .reverse()
              .map((c) => (
                <li key={c.id} className="p-3 text-sm">
                  <div className="flex items-center justify-between">
                    <div className="font-medium">
                      {c.prediction ?? "UNKNOWN"}
                      {typeof c.confidence === "number"
                        ? ` (${Math.round(c.confidence * 100)}%)`
                        : ""}
                    </div>
                    <div className="text-xs text-gray-500">
                      {c.createdAt ? fmt(c.createdAt) : ""}
                    </div>
                  </div>
                  <div className="mt-1 font-mono text-xs text-gray-500">
                    id: {c.id}
                  </div>
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  );
}