// All backend calls go through this file.
// In dev: proxy via vite.config.js → localhost:5000
// In prod: VITE_API_URL = https://your-render-url.onrender.com

const BASE = import.meta.env.VITE_API_URL ?? '';

async function apiFetch(path, params = {}) {
  const url = new URL(`${BASE}${path}`, window.location.origin);
  Object.entries(params).forEach(([k, v]) => v && url.searchParams.set(k, v));

  const res = await fetch(url.toString());
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || 'Request failed');
  }
  return res.json();
}

export const api = {
  /** Fetch all airports */
  airports: () => apiFetch('/api/airports'),

  /** Find optimal route between two IATA codes */
  route: (from, to, maxStops = 1) =>
    apiFetch('/api/route', { from, to, max_stops: maxStops }),

  /** Live flights between two airports */
  liveFlights: (departure, arrival) =>
    apiFetch('/api/flights/live', { departure, arrival }),

  /** Scheduled flights (optionally by date YYYY-MM-DD) */
  schedules: (departure, arrival, date) =>
    apiFetch('/api/schedules', { departure, arrival, date }),

  /** Health check */
  health: () => apiFetch('/api/health'),
};