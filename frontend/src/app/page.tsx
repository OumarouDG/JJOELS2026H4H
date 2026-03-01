"use client";
export const dynamic = "force-dynamic";

import { useEffect, useRef, useState } from "react";
import StatusBanner from "@/components/StatusBanner";
import CaptureButton from "@/components/CaptureButton";
import LiveGasChart from "@/components/LiveGasChart";
import FeatureTable from "@/components/FeatureTable";
import CaptureTimeline from "@/components/CaptureTimeline";
import type { CaptureResult, SensorSample } from "@/lib/types";
import { API_BASE } from "@/lib/api";

export default function HomePage() {
  const [result, setResult] = useState<CaptureResult | null>(null);
  const [samples, setSamples] = useState<SensorSample[]>([]);
  const [liveOk, setLiveOk] = useState<boolean>(true);

  // Avoid overlapping fetches if one stalls
  const fetchingRef = useRef(false);

  // Live Chart: HTTP polling from backend (/live)
  useEffect(() => {
    let alive = true;

    async function tick() {
      if (!alive) return;
      if (fetchingRef.current) return;
      fetchingRef.current = true;

      try {
        const res = await fetch(`${API_BASE}/live?tail=120`, {
          cache: "no-store",
          headers: { "Content-Type": "application/json" },
        });

        if (!res.ok) throw new Error(`live ${res.status}`);
        const data = (await res.json()) as { samples?: SensorSample[] };

        if (!alive) return;

        const incoming = Array.isArray(data?.samples) ? data.samples : [];
        setSamples(incoming.slice(-120));
        setLiveOk(true);
      } catch {
        if (!alive) return;
        // backend down / serial down / you sneezed near Windows
        setLiveOk(false);
      } finally {
        fetchingRef.current = false;
      }
    }

    // initial fetch immediately
    tick();

    // poll a few times per second; smooth enough without melting your laptop
    const id = window.setInterval(tick, 400);

    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, []);

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-8 p-8 bg-slate-50 min-h-screen">
      {/* Header  */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-black tracking-tighter text-slate-900">
            JJOELS<span className="text-indigo-600">2026</span>{" "}
            <span className="font-light text-slate-400">H4H</span>
          </h1>
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
            Real-Time Breath Biomarker Analysis
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="text-[10px] font-black text-slate-400 uppercase">
              System Status
            </div>

            <div
              className={`text-xs font-bold flex items-center gap-1 justify-end ${
                liveOk ? "text-emerald-500" : "text-rose-500"
              }`}
              title={liveOk ? "Polling /live OK" : "Backend not responding to /live"}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  liveOk ? "bg-emerald-500 animate-pulse" : "bg-rose-500"
                }`}
              />
              {liveOk ? "Node Active" : "Node Offline"}
            </div>
          </div>

          <div className="h-8 w-[1px] bg-slate-200 mx-2" />

          <div className="text-xs font-mono bg-indigo-50 text-indigo-600 px-3 py-1.5 rounded-full border border-indigo-100 font-bold">
            v2.0.4-PRO
          </div>
        </div>
      </div>

      <StatusBanner />

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-12">
        {/* Left Column: Input & Monitoring (7/12 width) */}
        <div className="lg:col-span-7 flex flex-col gap-8">
          <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-[0_4px_20px_rgb(0,0,0,0.03)]">
            <div className="mb-6 flex items-center justify-between">
              <h2 className="text-xs font-black uppercase tracking-widest text-slate-400">
                Control Interface
              </h2>
              <span className="text-[10px] text-slate-300 font-mono">ID: 882-X9</span>
            </div>

            {/* CaptureButton should call POST /record and directly return capture */}
            <CaptureButton onResult={setResult} />
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-[0_4px_20px_rgb(0,0,0,0.03)]">
            <LiveGasChart samples={samples} />
          </div>
        </div>

        {/* Right Column: Analysis Output (5/12 width) */}
        <div className="lg:col-span-5">
          <div className="sticky top-8 rounded-2xl border border-slate-200 bg-white p-8 shadow-[0_8px_30px_rgb(0,0,0,0.04)] min-h-[450px] flex flex-col justify-center">
            <div className="flex items-center justify-between mb-8">
              <h2 className="text-xs font-black uppercase tracking-widest text-slate-400">
                Analysis Engine
              </h2>
              {result && <div className="h-2 w-2 rounded-full bg-indigo-500 animate-pulse" />}
            </div>

            {!result ? (
              <div className="py-20 text-center border-2 border-dashed border-slate-100 rounded-2xl bg-slate-50/50">
                <p className="text-sm text-slate-400 font-medium">
                  Awaiting biometric signal...
                </p>
              </div>
            ) : (
              <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-700">
                {/* Confidence Hero */}
                <div className="flex items-center gap-6">
                  <div className="text-7xl font-black tracking-tighter text-indigo-600">
                    {Math.round((result.confidence ?? 0) * 100)}
                    <span className="text-2xl ml-1 text-indigo-300">%</span>
                  </div>
                  <div className="h-14 w-[1px] bg-slate-200" />
                  <div>
                    <div className="text-[10px] font-black uppercase tracking-wider text-slate-400 mb-1">
                      Confidence
                    </div>
                    <div className="text-xs font-bold text-slate-500 leading-tight">
                      Neural Pattern
                      <br />
                      Validated
                    </div>
                  </div>
                </div>

                {/* Status Classification Card */}
                <div
                  className={`relative overflow-hidden p-6 rounded-2xl border-l-[12px] transition-all ${
                    result.prediction?.toLowerCase() === "healthy"
                      ? "bg-emerald-50/60 border-emerald-500 text-emerald-900"
                      : "bg-amber-50/60 border-amber-500 text-amber-900"
                  }`}
                >
                  <div className="relative z-10">
                    <div className="text-[10px] uppercase font-black tracking-[0.2em] opacity-60 mb-2">
                      Predictive Result
                    </div>
                    <div className="text-3xl font-black tracking-tight italic uppercase">
                      {result.prediction}
                    </div>
                  </div>

                  {/* Backdrop Glow */}
                  <div
                    className={`absolute -right-8 -top-8 h-32 w-32 rounded-full blur-3xl opacity-30 ${
                      result.prediction?.toLowerCase() === "healthy"
                        ? "bg-emerald-400"
                        : "bg-amber-400"
                    }`}
                  />
                </div>

                {/* Feature Metric Grid */}
                <div className="grid grid-cols-2 gap-4">
                  {Object.entries(result.features || {}).map(([key, val]) => (
                    <div
                      key={key}
                      className="bg-slate-50/80 p-4 rounded-xl border border-slate-100 group hover:border-indigo-200 transition-all duration-300"
                    >
                      <div className="text-[9px] uppercase font-black text-slate-400 tracking-wider group-hover:text-indigo-400">
                        {key}
                      </div>
                      <div className="text-base font-mono font-bold text-slate-700 mt-1">
                        {String(val)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Footer Details */}
      <div className="grid grid-cols-1 gap-8 mt-4">
        <FeatureTable features={result?.features} />
        <CaptureTimeline title="Historical Baseline" />
      </div>
    </main>
  );
}