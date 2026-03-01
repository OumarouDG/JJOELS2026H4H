"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { SensorSample } from "@/lib/types";

type Props = {
  title?: string;
  samples?: SensorSample[];
};

function formatTime(t: number) {
  const d = new Date(t);
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${mm}:${ss}`;
}

export default function LiveGasChart({ title = "Live Gas (Ω)", samples }: Props) {
  const data =
    samples?.map((s) => ({
      t: s.t,
      time: formatTime(s.t),
      gas_ohms: s.gas_ohms,
    })) ?? [];

  return (
    <div className="rounded-lg border p-4">
      <div className="mb-3 font-semibold">{title}</div>
        
      {!data.length ? (
        <div className="text-sm text-gray-500">
          No live samples yet. Start sensor streaming or use mock data.
        </div>
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <XAxis dataKey="time" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line type="monotone" dataKey="gas_ohms" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}