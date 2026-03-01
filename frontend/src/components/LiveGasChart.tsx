"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { useEffect, useState } from "react";

type ChartPoint = {
  t: number;
  time: string;
  gas_ohms: number;
};

function formatTime(t: number) {
  const d = new Date(t);
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${mm}:${ss}`;
}

export default function LiveGasChart({
  title = "Live Gas (Ω)",
}: {
  title?: string;
}) {
  const [data, setData] = useState<ChartPoint[]>([]);

  useEffect(() => {
    const ws = new WebSocket("ws://localhost:8000/ws");

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);

      // ignore prediction broadcasts
      if (!msg.gas) return;

      const now = Date.now();

      const newPoint: ChartPoint = {
        t: now,
        time: formatTime(now),
        gas_ohms: msg.gas,
      };

      // keep last ~80 points (smooth scrolling chart)
      setData((prev) => [...prev.slice(-80), newPoint]);
    };

    ws.onerror = () => {
      console.log("WebSocket error");
    };

    return () => ws.close();
  }, []);

  return (
    <div className="rounded-lg border p-4">
      <div className="mb-3 font-semibold">{title}</div>

      {!data.length ? (
        <div className="text-sm text-gray-500">
          Press Record to begin live sensor streaming.
        </div>
      ) : (
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <XAxis dataKey="time" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="gas_ohms"
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}