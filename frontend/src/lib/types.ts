// Shared frontend data contracts.
// These mirror backend responses.

export type CaptureResult = {
  id?: string;
  createdAt?: string;
  features?: Record<string, number>;
  prediction?: string;
  confidence?: number;
};