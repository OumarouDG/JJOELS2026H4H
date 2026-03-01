"use client";

type CaptureMockResult = {
  mock: boolean;
};

type Props = {
  onResult: (r: CaptureMockResult) => void;
};

export default function CaptureButton({ onResult }: Props) {
  return (
    <button
      onClick={() => onResult({ mock: true })}
      className="rounded-lg border px-4 py-2 font-medium hover:bg-gray-100"
    >
      Capture 10s
    </button>
  );
}