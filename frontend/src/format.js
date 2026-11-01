export const RISK_COLOR = {
  L: "#2f9e6b",
  M: "#c8922a",
  H: "#e07a2f",
  S: "#d24b4b",
  N: "#7a3e72",
  X: "#8b97a6",
  low: "#2f9e6b",
  moderate: "#c8922a",
  high: "#e07a2f",
  severe: "#d24b4b",
  no_travel: "#7a3e72",
};

export const RISK_LABEL = {
  low: "Low",
  moderate: "Moderate",
  high: "High",
  severe: "Severe",
  no_travel: "No travel",
  L: "Low",
  M: "Moderate",
  H: "High",
  S: "Severe",
  N: "No travel",
  X: "No forecast",
};

export const ROUTE_COLOR = {
  A: "#1d6fbf",
  B: "#b86e12",
  C: "#6b4c9a",
};

export function formatDuration(seconds) {
  const total = Math.max(0, Math.round(Number(seconds) || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.round((total % 3600) / 60);
  if (hours <= 0) return `${minutes}m`;
  return `${hours}h ${minutes}m`;
}

export function formatWhen(iso) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString([], {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function addHours(iso, hours) {
  const date = new Date(iso);
  return new Date(date.getTime() + hours * 60 * 60 * 1000);
}

export function defaultDepartureInput() {
  const date = new Date();
  date.setMinutes(0, 0, 0);
  date.setHours(date.getHours() + 1);
  return toLocalInput(date);
}

export function departureBounds() {
  const min = new Date();
  min.setMinutes(0, 0, 0);
  const max = new Date(min.getTime() + 6 * 24 * 60 * 60 * 1000);
  return { min: toLocalInput(min), max: toLocalInput(max) };
}

function toLocalInput(date) {
  const pad = (value) => String(value).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
