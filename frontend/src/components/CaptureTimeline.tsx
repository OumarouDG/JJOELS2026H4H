import { useEffect, useState } from "react";
import { getCaptures } from "@/lib/api";
import type { CaptureResult } from "@/lib/types";


type Props = {
  title?: string;
  refreshMs?: number;
  items?: CaptureResult[];
};

export default function CaptureTimeline({
  title = "Health Analysis Feed",
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
    <div className="card rounded-xl shadow-sm overflow-hidden">
      <div className="border-b bg-gray-50/50 flex items-center justify-between">
        <h2 className="font-bold text-gray-800">{title}</h2>
        <span className="text-xs font-medium px-2 py-1 rounded-full bg-gray-200 text-gray-600">
          {loading ? "Syncing..." : "Live"}
        </span>
      </div>

      <div className="max-h-[400px] overflow-auto">
        {!rows.length ? (
          <div className="p-8 text-center text-sm text-gray-400">
            Waiting for incoming data...
          </div>
        ) : (
          <ul className="divide-y divide-gray-100">
            {rows
              .slice()
              .reverse()
              .map((c) => {
                const isSick = c.prediction?.toLowerCase() === "sick";
                const confidencePercent = Math.round((c.confidence ?? 0) * 100);

                return (
                  <li key={c.id} className="p-4 hover:bg-gray-50 transition-colors">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        {/* Status Indicator */}
                        <span className={`h-2.5 w-2.5 rounded-full ${isSick ? 'bg-red-500 animate-pulse' : 'bg-green-500'}`} />
                        <span className={`font-bold uppercase tracking-wide text-sm ${isSick ? 'text-red-700' : 'text-green-700'}`}>
                          {c.prediction ?? "Processing"}
                        </span>
                      </div>
                      <span className="text-xs font-semibold text-gray-500">
                        {confidencePercent}% Match
                      </span>
                    </div>

                    {/* Confidence Meter */}
                    <div className="w-full bg-gray-100 rounded-full h-1.5">
                      <div 
                        className={`h-1.5 rounded-full transition-all duration-500 ${isSick ? 'bg-red-400' : 'bg-green-400'}`}
                        style={{ width: `${confidencePercent}%` }}
                      />
                    </div>
                  </li>
                );
              })}
          </ul>
        )}
      </div>
    </div>
  );
}