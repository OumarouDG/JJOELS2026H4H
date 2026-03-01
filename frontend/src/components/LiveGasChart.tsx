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
    <div className="card">
      <div className="mb-3 font-semibold">{title}</div>
        
      {!data.length ? (
        <div className="text-sm text-gray-500">
          No live samples yet. Start sensor streaming or use mock data.
        </div>
      ) : (
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 10, right: 30, left: 50, bottom: 40 }}>
              <XAxis
                dataKey="time"
                tick={{ fontSize: 12, fill: "#111827", fontWeight: 700 }}
                interval="preserveStartEnd"
                axisLine={{ stroke: "#111827", strokeWidth: 2 }}
                tickLine={{ stroke: "#d1d5db", strokeWidth: 1 }}
                label={{ value: "Time (mm:ss)", position: "bottom", offset: 20, style: { fill: "#111827", fontSize: 12, fontWeight: 700 } }}
              />
              <YAxis
                tick={{ fontSize: 12, fill: "#111827", fontWeight: 700 }}
                axisLine={{ stroke: "#111827", strokeWidth: 2 }}
                tickLine={{ stroke: "#d1d5db", strokeWidth: 1 }}
                label={{ value: "Gas (Ω)", angle: -90, position: "left", offset: 40, style: { fill: "#111827", fontSize: 12, fontWeight: 700 } }}
              />
              <Tooltip />
              <Line type="monotone" dataKey="gas_ohms" stroke="#8884d8" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}