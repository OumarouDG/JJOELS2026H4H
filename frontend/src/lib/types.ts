// Shared frontend data contracts.
// Keep these stable so UI components don't break when backend changes slightly.

export type SensorSample = {
  t: number; // epoch ms
  tempC: number;
  humidity: number;
  pressure_hPa: number;
  gas_ohms: number;
};

export type CaptureResult = {
  id: string;
  createdAt: string; // ISO string
  // optional raw window if backend returns it
  window?: SensorSample[];
  // extracted features used by the model
  features: Record<string, number>;
  prediction?: string;
  confidence?: number; // 0..1
};

export type Metrics = {
  accuracy: number; // 0..1
  labels: string[];
  feature_names: string[];
  confusion_matrix_url?: string;
};

export type ApiError = {
  message: string;
  status?: number;
  details?: unknown;
};