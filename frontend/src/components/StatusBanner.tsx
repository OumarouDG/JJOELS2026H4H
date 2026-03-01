"use client";

export default function StatusBanner() {
  return (
    <div className="w-full rounded-lg border p-3 text-sm">
      <div className="font-semibold">System Status</div>
      <div className="opacity-70">
        Frontend running. Awaiting backend connection.
      </div>
    </div>
  );
}