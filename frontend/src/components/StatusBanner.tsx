"use client";

import { useEffect, useState } from "react";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function StatusBanner() {
  const [status, setStatus] = useState<"checking" | "online" | "offline">(
    "checking"
  );

  useEffect(() => {
    async function check() {
      try {
        const res = await fetch(`${API_URL}/metrics`, {
          cache: "no-store",
        });

        setStatus(res.ok ? "online" : "offline");
      } catch {
        setStatus("offline");
      }
    }

    check();
  }, []);

  const color =
    status === "online"
      ? "bg-green-100 text-green-700"
      : status === "offline"
      ? "bg-red-100 text-red-700"
      : "bg-yellow-100 text-yellow-700";

  return (
    <div className={`rounded-lg px-4 py-2 text-sm ${color}`}>
      API: {API_URL} • Backend: {status}
    </div>
  );
}