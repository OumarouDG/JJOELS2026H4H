"use client";
export const dynamic = "force-dynamic";

import { useEffect, useMemo, useRef, useState } from "react";
import StatusBanner from "@/components/StatusBanner";
import CaptureButton from "@/components/CaptureButton";
import LiveGasChart from "@/components/LiveGasChart";
import FeatureTable from "@/components/FeatureTable";
import CaptureTimeline from "@/components/CaptureTimeline";
import type { CaptureResult, SensorSample } from "@/lib/types";
import { API_BASE } from "@/lib/api";

type EffectMode = "none" | "confetti" | "risk";

function normalizePrediction(raw?: string | null) {
  const p = (raw ?? "").trim().toUpperCase();
  if (p === "LOW_LOAD") return "LOW_LOAD";
  if (p === "HIGH_LOAD") return "HIGH_LOAD";
  if (p === "HEALTHY") return "LOW_LOAD";
  return p || "UNKNOWN";
}

function displayPredictionLabel(norm: string) {
  if (norm === "LOW_LOAD") return "Clear";
  if (norm === "HIGH_LOAD") return "Risk";
  if (norm === "ERROR") return "Error";
  if (norm === "UNKNOWN") return "Unknown";
  return norm.replaceAll("_", " ");
}

export default function HomePage() {
  const [result, setResult] = useState<CaptureResult | null>(null);
  const [samples, setSamples] = useState<SensorSample[]>([]);
  const [liveOk, setLiveOk] = useState<boolean>(true);
  const [capturing, setCapturing] = useState<boolean>(false);
  const [effect, setEffect] = useState<EffectMode>("none");

  const fetchingRef = useRef(false);

  useEffect(() => {
    if (!result?.prediction) return;
    const norm = normalizePrediction(result.prediction);

    if (norm === "LOW_LOAD") {
      setEffect("confetti");
      const t = window.setTimeout(() => setEffect("none"), 1600);
      return () => window.clearTimeout(t);
    }

    if (norm === "HIGH_LOAD") {
      setEffect("risk");
      const t = window.setTimeout(() => setEffect("none"), 1600);
      return () => window.clearTimeout(t);
    }
  }, [result?.prediction]);

  useEffect(() => {
    if (!capturing) return;

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
        const data = await res.json();

        if (!alive) return;

        const incoming = Array.isArray(data?.samples) ? data.samples : [];
        setSamples(incoming.slice(-120));
        setLiveOk(true);

        if (data?.capturing === false) {
          setCapturing(false);
        }
      } catch {
        if (!alive) return;
        setLiveOk(false);
      } finally {
        fetchingRef.current = false;
      }
    }

    tick();
    const id = window.setInterval(tick, 200);

    return () => {
      alive = false;
      window.clearInterval(id);
    };
  }, [capturing]);

  const normalizedPrediction = useMemo(
    () => normalizePrediction(result?.prediction),
    [result?.prediction]
  );

  const prettyPrediction = useMemo(
    () => displayPredictionLabel(normalizedPrediction),
    [normalizedPrediction]
  );

  const actionNote = useMemo(() => {
    if (!result?.prediction) return null;

    if (normalizedPrediction === "LOW_LOAD") {
      return "Looks clear. If you feel off anyway, trust your body and monitor symptoms.";
    }
    if (normalizedPrediction === "HIGH_LOAD") {
      return "Risk detected. Consider consulting a medical professional, especially if symptoms are present.";
    }
    if (normalizedPrediction === "ERROR") {
      return "Inference failed. Try another capture.";
    }
    return "Result received. Consider taking another sample for confirmation.";
  }, [result?.prediction, normalizedPrediction]);

  const statusCardClasses = useMemo(() => {
    if (normalizedPrediction === "LOW_LOAD") {
      return "bg-emerald-50/60 border-emerald-500 text-emerald-900";
    }
    if (normalizedPrediction === "HIGH_LOAD") {
      return "bg-rose-50/60 border-rose-500 text-rose-900";
    }
    return "bg-amber-50/60 border-amber-500 text-amber-900";
  }, [normalizedPrediction]);

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-5 p-4 sm:p-6 bg-slate-50 min-h-screen">
      {effect !== "none" && (
        <div className="pointer-events-none fixed inset-0 z-[60] overflow-hidden">
          {effect === "confetti" ? (
            <div className="absolute inset-0">
              {Array.from({ length: 90 }).map((_, i) => (
                <span
                  key={i}
                  className="confetti-piece"
                  style={{
                    left: `${Math.random() * 100}%`,
                    top: `-10%`,
                    animationDelay: `${Math.random() * 0.25}s`,
                    transform: `rotate(${Math.random() * 360}deg)`,
                  }}
                />
              ))}
            </div>
          ) : (
            <div className="absolute inset-0">
              <div className="risk-flash" />
              <div className="risk-scanlines" />
            </div>
          )}
        </div>
      )}

      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tighter text-slate-900">
            SenseAir<span className="text-indigo-600">2026</span>{" "}
            <span className="font-light text-slate-400">H4H</span>
          </h1>
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-slate-400">
            Real-Time Breath Biomarker Analysis
          </p>
        </div>

        <div className="text-xs font-mono bg-indigo-50 text-indigo-600 px-3 py-1.5 rounded-full border border-indigo-100 font-bold">
          v2.0.4-PRO
        </div>
      </div>

      <StatusBanner />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-12">
        <div className="lg:col-span-7 flex flex-col gap-5">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-xs font-black uppercase tracking-widest text-slate-400">
                Control Interface
              </h2>
              <span className="text-[10px] text-slate-300 font-mono">
                ID: 882-X9
              </span>
            </div>

            <CaptureButton
              onResult={(cap) => setResult(cap)}
              onCaptureState={(isOn) => {
                setCapturing(isOn);
                if (isOn) {
                  setSamples([]);
                  setResult(null);
                  setLiveOk(true);
                }
              }}
            />
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-3 shadow">
            <LiveGasChart samples={samples} />
          </div>
        </div>

        <div className="lg:col-span-5">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 sm:p-6 shadow min-h-[420px] flex flex-col justify-center">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xs font-black uppercase tracking-widest text-slate-400">
                Analysis
              </h2>
              {result && <div className="h-2 w-2 rounded-full bg-indigo-500 animate-pulse" />}
            </div>

            {!result ? (
              <div className="py-16 text-center border-2 border-dashed border-slate-100 rounded-2xl bg-slate-50/50">
                <p className="text-sm text-slate-400 font-medium">
                  Awaiting biometric signal...
                </p>
              </div>
            ) : (
              <div className="space-y-7">
                <div className="flex items-center gap-5">
                  <div className="text-6xl sm:text-7xl font-black tracking-tighter text-indigo-600">
                    {Math.round((result.confidence ?? 0) * 100)}
                    <span className="text-2xl ml-1 text-indigo-300">%</span>
                  </div>
                </div>

                <div className={`relative overflow-hidden p-5 rounded-2xl border-l-[12px] ${statusCardClasses}`}>
                  <div className="relative z-10">
                    <div className="text-[10px] uppercase font-black tracking-[0.2em] opacity-70 mb-2">
                      Predictive Result
                    </div>
                    <div className="text-3xl font-black tracking-tight italic uppercase">
                      {prettyPrediction}
                    </div>
                    {actionNote && (
                      <p className="mt-3 text-sm font-medium opacity-90">
                        {actionNote}
                      </p>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  {Object.entries(result.features || {}).map(([key, val]) => (
                    <div
                      key={key}
                      className="bg-slate-50/80 p-3 rounded-xl border border-slate-100"
                    >
                      <div className="text-[9px] uppercase font-black text-slate-400 tracking-wider">
                        {key}
                      </div>
                      <div className="text-sm sm:text-base font-mono font-bold text-slate-700 mt-1">
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

      <div className="grid grid-cols-1 gap-6 mt-2">
        <FeatureTable features={result?.features} />
        <CaptureTimeline title="Historical Baseline" />
      </div>
    </main>
  );
}