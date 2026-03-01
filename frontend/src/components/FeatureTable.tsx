"use client";

type Props = {
  title?: string;
  features?: Record<string, number>;
  // Optional: limit rows for readability
  maxRows?: number;
};

function formatValue(v: number) {
  if (!Number.isFinite(v)) return String(v);
  // Keep it readable: big gas numbers shouldn't look like scientific soup unless needed
  if (Math.abs(v) >= 1000) return Math.round(v).toString();
  if (Math.abs(v) >= 10) return v.toFixed(2);
  return v.toFixed(4);
}

export default function FeatureTable({ title = "Features", features, maxRows = 50 }: Props) {
  const entries = features ? Object.entries(features) : [];

  // Sort by key so it doesn't jump around between renders
  entries.sort(([a], [b]) => a.localeCompare(b));

  const shown = entries.slice(0, maxRows);

  return (
    <div className="card">
      <div className="mb-3 flex items-center justify-between">
        <div className="font-semibold">{title}</div>
        <div className="text-xs text-gray-700">
          {entries.length ? `${Math.min(entries.length, maxRows)} / ${entries.length}` : "0"}
        </div>
      </div>

      {!entries.length ? (
        <div className="text-sm text-gray-500">No features yet. Capture first.</div>
      ) : (
        <div className="max-h-80 overflow-auto rounded border">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-gray-100">
              <tr className="border-b">
                <th className="px-3 py-2 text-left font-medium text-gray-700">Feature</th>
                <th className="px-3 py-2 text-right font-medium text-gray-700">Value</th>
              </tr>
            </thead>
            <tbody>
              {shown.map(([k, v]) => (
                <tr key={k} className="border-b last:border-b-0">
                  <td className="px-3 py-2 font-mono text-xs">{k}</td>
                  <td className="px-3 py-2 text-right font-mono text-xs">
                    {formatValue(v)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {entries.length > maxRows && (
        <div className="mt-2 text-xs text-gray-700">
          Showing first {maxRows}. (Yeah, we’re not printing 400 features to impress anyone.)
        </div>
      )}
    </div>
  );
}