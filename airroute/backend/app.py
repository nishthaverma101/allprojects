import os
import time
import math
import heapq
import threading
import functools
from datetime import datetime
from collections import defaultdict

import pandas as pd
import requests
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app, origins=os.getenv("ALLOWED_ORIGINS", "*").split(","))

limiter = Limiter(get_remote_address, app=app, default_limits=["60 per minute"])

# ── Config ────────────────────────────────────────────────────────────────────
API_KEY  = os.getenv("AVIATION_STACK_API_KEY", "")
BASE_URL = "http://api.aviationstack.com/v1"

CACHE_TTL_AIRPORTS  = 3600
CACHE_TTL_FLIGHTS   = 300
CACHE_TTL_SCHEDULES = 600

# ── Thread-safe cache ─────────────────────────────────────────────────────────
_cache: dict = {}
_cache_lock = threading.RLock()

def cache_get(key: str):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and time.time() < entry[1]:
            return entry[0]
    return None

def cache_set(key: str, value, ttl: int):
    with _cache_lock:
        _cache[key] = (value, time.time() + ttl)

# ── Request deduplication ─────────────────────────────────────────────────────
# Only 1 thread fetches per unique key; all others wait and share result.
# Prevents deadlock and thundering-herd on the paid API.
_inflight_locks: dict = {}
_inflight_results: dict = {}
_inflight_meta_lock = threading.Lock()

def fetch_with_dedup(cache_key: str, fetch_fn, ttl: int):
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    with _inflight_meta_lock:
        if cache_key in _inflight_locks:
            event = _inflight_locks[cache_key]
            is_leader = False
        else:
            event = threading.Event()
            _inflight_locks[cache_key] = event
            is_leader = True

    if is_leader:
        try:
            result = fetch_fn()
            cache_set(cache_key, result, ttl)
            _inflight_results[cache_key] = result
        finally:
            with _inflight_meta_lock:
                _inflight_locks.pop(cache_key, None)
            event.set()
    else:
        event.wait(timeout=10)
        result = _inflight_results.get(cache_key) or cache_get(cache_key)

    return result

# ── Airport loading (singleton, thread-safe) ──────────────────────────────────
_airports_cache = None
_airports_lock  = threading.Lock()

def load_airports():
    global _airports_cache
    if _airports_cache is not None:
        return _airports_cache
    with _airports_lock:
        if _airports_cache is not None:
            return _airports_cache
        try:
            df = pd.read_csv("in-airports.csv")
            df = df[
                df["type"].isin(["large_airport", "medium_airport"]) &
                (df["scheduled_service"] == 1) &
                df["iata_code"].notna()
            ]
            _airports_cache = [
                {
                    "code":         str(row["iata_code"]),
                    "name":         str(row["name"]),
                    "location":     f"{row['municipality']}, {row['region_name']}",
                    "latitude":     float(row["latitude_deg"]),
                    "longitude":    float(row["longitude_deg"]),
                    "safetyRating": 95,
                    "failureRate":  0.003,
                }
                for _, row in df.iterrows()
            ]
        except Exception as e:
            app.logger.error(f"Airport CSV load failed: {e}")
            _airports_cache = []
    return _airports_cache

# ── Haversine distance (km) ───────────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

# ── Dijkstra route finder ─────────────────────────────────────────────────────
def dijkstra(airports, src: str, dst: str, max_stops: int = 1) -> dict:
    idx = {a["code"]: i for i, a in enumerate(airports)}
    if src not in idx:
        return {"error": f"Airport '{src}' not found"}
    if dst not in idx:
        return {"error": f"Airport '{dst}' not found"}

    n   = len(airports)
    adj = defaultdict(list)

    for i in range(n):
        for j in range(i + 1, n):
            d = haversine(
                airports[i]["latitude"], airports[i]["longitude"],
                airports[j]["latitude"], airports[j]["longitude"],
            )
            if d <= 3000:
                adj[i].append((d, j))
                adj[j].append((d, i))

    si, di = idx[src], idx[dst]
    INF  = float("inf")
    dist = [INF] * n
    hops = [0]   * n
    prev = [-1]  * n
    dist[si] = 0.0
    heap = [(0.0, si)]

    while heap:
        cost, u = heapq.heappop(heap)
        if cost > dist[u]:
            continue
        if u == di:
            break
        if hops[u] > max_stops:
            continue
        for w, v in adj[u]:
            nc = cost + w
            if nc < dist[v]:
                dist[v]  = nc
                hops[v]  = hops[u] + 1
                prev[v]  = u
                heapq.heappush(heap, (nc, v))

    if dist[di] == INF:
        return {"error": "No route found within connection limit"}

    path, cur = [], di
    while cur != -1:
        path.append(airports[cur]["code"])
        cur = prev[cur]
    path.reverse()

    return {
        "path":           path,
        "total_distance": round(dist[di], 1),
        "stops":          len(path) - 2,
        "airports":       [airports[idx[c]] for c in path],
    }

# ── Aviation Stack helper ─────────────────────────────────────────────────────
def aviation_get(endpoint: str, params: dict):
    if not API_KEY:
        app.logger.warning("AVIATION_STACK_API_KEY not configured")
        return None
    try:
        params["access_key"] = API_KEY
        r = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=8)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        app.logger.error(f"Aviation API [{endpoint}] error: {e}")
        return None

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "time": datetime.utcnow().isoformat()})


@app.route("/api/airports")
@limiter.limit("30 per minute")
def get_airports():
    return jsonify(load_airports())


@app.route("/api/route")
@limiter.limit("20 per minute")
def get_route():
    src   = (request.args.get("from", "") or "").upper().strip()
    dst   = (request.args.get("to",   "") or "").upper().strip()
    stops = min(int(request.args.get("max_stops", 1)), 3)

    if not src or not dst:
        return jsonify({"error": "from and to parameters required"}), 400
    if src == dst:
        return jsonify({"error": "Source and destination must be different"}), 400

    airports  = load_airports()
    cache_key = f"route:{src}:{dst}:{stops}"

    result = fetch_with_dedup(cache_key, lambda: dijkstra(airports, src, dst, stops), CACHE_TTL_FLIGHTS)
    if "error" in result:
        return jsonify(result), 404
    return jsonify(result)


@app.route("/api/flights/live")
@limiter.limit("10 per minute")
def get_live_flights():
    dep = (request.args.get("departure", "") or "").upper().strip()
    arr = (request.args.get("arrival",   "") or "").upper().strip()

    if not dep or not arr:
        return jsonify({"error": "departure and arrival required"}), 400

    cache_key = f"live:{dep}:{arr}"

    def fetch():
        data = aviation_get("flights", {
            "dep_iata": dep, "arr_iata": arr,
            "limit": 10, "flight_status": "active",
        })
        if not data or "data" not in data:
            return []
        return [
            {
                "flight_number":  f.get("flight",    {}).get("iata", "N/A"),
                "airline":        f.get("airline",   {}).get("name", "N/A"),
                "status":         f.get("flight_status", "N/A"),
                "departure_time": f.get("departure", {}).get("scheduled", "N/A"),
                "arrival_time":   f.get("arrival",   {}).get("scheduled", "N/A"),
                "delay":          f.get("departure", {}).get("delay", 0),
            }
            for f in data["data"]
        ]

    return jsonify({"data": fetch_with_dedup(cache_key, fetch, CACHE_TTL_FLIGHTS)})


@app.route("/api/schedules")
@limiter.limit("10 per minute")
def get_schedules():
    dep  = (request.args.get("departure", "") or "").upper().strip()
    arr  = (request.args.get("arrival",   "") or "").upper().strip()
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))

    if not dep or not arr:
        return jsonify({"error": "departure and arrival required"}), 400

    cache_key = f"sched:{dep}:{arr}:{date}"

    def fetch():
        data = aviation_get("flights", {
            "dep_iata": dep, "arr_iata": arr,
            "flight_status": "scheduled", "flight_date": date,
        })
        if not data or "data" not in data:
            return []
        return [
            {
                "flight_number": f.get("flight",  {}).get("iata", "N/A"),
                "airline":       f.get("airline", {}).get("name", "N/A"),
                "departure": {
                    "scheduled": f.get("departure", {}).get("scheduled", "N/A"),
                    "terminal":  f.get("departure", {}).get("terminal",  "N/A"),
                },
                "arrival": {
                    "scheduled": f.get("arrival", {}).get("scheduled", "N/A"),
                    "terminal":  f.get("arrival",  {}).get("terminal",  "N/A"),
                },
            }
            for f in data["data"]
            if f.get("flight_status") == "scheduled"
        ]

    return jsonify({"data": fetch_with_dedup(cache_key, fetch, CACHE_TTL_SCHEDULES),
                    "total": len(fetch_with_dedup(cache_key, fetch, CACHE_TTL_SCHEDULES))})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)