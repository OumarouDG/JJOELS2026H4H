// Centralized API client.
// All backend calls go through this file.

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function postCapture(seconds = 10) {
  console.log("Mock capture request:", seconds);

  // TEMP mock response
  return {
    mock: true,
    seconds,
  };
}