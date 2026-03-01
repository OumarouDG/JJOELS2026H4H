/**
 * ===============================
 * API CONTRACT (Frontend ↔ Backend)
 * ===============================
 *
 * Base URL:
 *   process.env.NEXT_PUBLIC_API_URL
 *
 * Endpoints expected:
 *
 * GET /metrics
 *   -> Metrics
 *
 * GET /captures
 *   -> CaptureResult[]
 *
 * POST /capture
 *   body: { seconds: number }
 *   -> CaptureResult
 *
 * POST /infer (optional)
 *   body: { features: Record<string, number> }
 *   -> CaptureResult
 *
 * Behavior:
 * - If backend is unavailable, mock data is returned.
 * - UI should always render safely without backend running.
 *
 * Single source of truth:
 *   types.ts defines all shared structures.
 */
import type { CaptureResult, Metrics, SensorSample } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

async function safeJson(res: Response) {
  const text = await res.text().catch(() => "");
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return text || null;
  }
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  const body = await safeJson(res);

  if (!res.ok) {
    throw new Error(
      `API ${res.status} ${res.statusText} on ${path}: ${JSON.stringify(body)}`
    );
  }

  return body as T;
}

function mockMetrics(): Metrics {
  return {
    accuracy: 0.0,
    labels: ["NEGATIVE", "POSITIVE"],
    feature_names: [],
  };
}

export async function getMetrics(): Promise<Metrics> {
  try {
    return await http<Metrics>("/metrics");
  } catch (e) {
    console.warn("getMetrics fallback:", e);
    return mockMetrics();
  }
}

export async function getCaptures(): Promise<CaptureResult[]> {
  try {
    return await http<CaptureResult[]>("/captures");
  } catch (e) {
    console.warn("getCaptures fallback:", e);
    return [];
  }
}

export async function getLive(tail = 120): Promise<SensorSample[]> {
  const res = await http<{ samples: SensorSample[] }>(`/live?tail=${tail}`);
  return res.samples ?? [];
}

export async function postRecord(durationMs = 5000): Promise<CaptureResult> {
  const res = await http<{ ok: boolean; capture?: CaptureResult; error?: string }>(
    `/record?duration_ms=${durationMs}`,
    { method: "POST" }
  );

  if (!res.ok || !res.capture) {
    throw new Error(res.error || "Record failed");
  }

  return res.capture;
}