const API_BASE = import.meta.env.DEV ? "http://127.0.0.1:8000" : "";

async function readJson(response) {
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "Request failed.");
  }
  return data;
}

export async function searchPlaces(query) {
  const data = await fetch(`${API_BASE}/api/geocode/?q=${encodeURIComponent(query)}`).then(readJson);
  return data.results || [];
}

export function analyzeTrip(body) {
  return fetch(`${API_BASE}/api/analyze/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(readJson);
}
