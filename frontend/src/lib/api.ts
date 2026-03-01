import type { CaptureResult, Metrics } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// --- Helpers ---
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

  if (!res.ok) {
    const body = await safeJson(res);
    throw new Error(
      `API ${res.status} ${res.statusText} on ${path}: ${JSON.stringify(body)}`
    );
  }

  return (await res.json()) as T;
}

// --- Mock fallbacks (if backend isn't up) ---
function mockMetrics(): Metrics {
  return {
    accuracy: 0.0,
    labels: ["NEGATIVE", "POSITIVE"],
    feature_names: [],
  };
}

function mockCapture(): CaptureResult {
  const now = new Date().toISOString();
  return {
    id: `mock-${Date.now()}`,
    createdAt: now,
    features: { mock: 1 },
    prediction: "UNKNOWN",
    confidence: 0,
  };
}

// --- API functions ---
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

export async function postCapture(seconds = 10): Promise<CaptureResult> {
  try {
    return await http<CaptureResult>("/capture", {
      method: "POST",
      body: JSON.stringify({ seconds }),
    });
  } catch (e) {
    console.warn("postCapture fallback:", e);
    return mockCapture();
  }
}

// Optional: if backend wants direct inference call
export async function postInfer(
  features: Record<string, number>
): Promise<CaptureResult> {
  try {
    return await http<CaptureResult>("/infer", {
      method: "POST",
      body: JSON.stringify({ features }),
    });
  } catch (e) {
    console.warn("postInfer fallback:", e);
    return mockCapture();
  }
}