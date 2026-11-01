import { useEffect, useRef, useState } from "react";
import { searchPlaces } from "../api";
import {
  RISK_COLOR,
  RISK_LABEL,
  ROUTE_COLOR,
  departureBounds,
  formatDuration,
  formatWhen,
} from "../format";

const BOUNDS = departureBounds();

export default function Sidebar({
  departure,
  setDeparture,
  load,
  setLoad,
  interval,
  setInterval,
  loading,
  error,
  result,
  selectedId,
  onSelect,
  onCheckpoint,
  onSubmit,
}) {
  return (
    <aside className="sidebar">
      <header className="brand">
        <span className="mark">SP</span>
        <div>
          <p className="kicker">Spotter</p>
          <h1>Weather-aware truck routing</h1>
        </div>
      </header>

      <form className="trip-form" onSubmit={onSubmit}>
        <PlaceField name="origin" label="Origin" placeholder="Dallas, TX" />
        <PlaceField name="destination" label="Destination" placeholder="Houston, TX" />
        <label>
          Departure
          <input
            type="datetime-local"
            value={departure}
            min={BOUNDS.min}
            max={BOUNDS.max}
            onChange={(event) => setDeparture(event.target.value)}
            required
          />
        </label>
        <div className="split">
          <label>
            Load weight (lb)
            <input
              type="number"
              min="1"
              max="250000"
              step="1"
              value={load}
              onChange={(event) => setLoad(event.target.value)}
              required
            />
          </label>
          <label>
            Sample every
            <select value={interval} onChange={(event) => setInterval(event.target.value)}>
              <option value="10">10 miles</option>
              <option value="25">25 miles</option>
              <option value="50">50 miles</option>
            </select>
          </label>
        </div>
        <button className="primary" type="submit" disabled={loading}>
          {loading ? "Checking routes and weather…" : "Find the safest route"}
        </button>
      </form>

      {error && <p className="banner error" role="alert">{error}</p>}
      {result?.note && <p className="banner">{result.note}</p>}
      {result?.routes?.[0]?.no_travel_miles > 0 && (
        <p className="banner warn">
          Every option crosses no-travel weather. Option A is the least dangerous, not a clear route.
        </p>
      )}

      {!result && !loading && (
        <p className="intro">
          Plan a trip to compare routes by severe miles, high-risk miles, average risk, and travel time.
          Checkpoints use the truck&apos;s estimated arrival time.
        </p>
      )}

      <div className="routes">
        {result?.routes?.map((route) => (
          <article
            key={route.id}
            className={route.id === selectedId ? "route-card selected" : "route-card"}
            style={{ "--route": ROUTE_COLOR[route.id] }}
          >
            <button type="button" className="route-hit" onClick={() => onSelect(route.id)}>
              <span className="route-top">
                <span className="route-name">{route.name}</span>
                {route.recommended && <span className="badge">Recommended</span>}
              </span>
              <span className="route-metrics">
                <span>{route.distance_miles.toFixed(1)} mi</span>
                <span>{formatDuration(route.duration_seconds)}</span>
                <span>Avg {route.average_risk.toFixed(2)} / 5</span>
              </span>
              <RiskBar route={route} />
              <span className="route-buckets">
                No travel {route.no_travel_miles.toFixed(1)} · Severe {route.severe_miles.toFixed(1)} · High{" "}
                {route.high_miles.toFixed(1)}
              </span>
              {route.reason && <span className="reason">{route.reason}</span>}
            </button>
            {route.id === selectedId && (
              <CheckpointList route={route} onCheckpoint={onCheckpoint} />
            )}
          </article>
        ))}
      </div>

      <details className="rules">
        <summary>How a route is scored</summary>
        <p>Weather is sampled every 10, 25, or 50 miles at the estimated arrival time. The checkpoint risk is the worst of wind, rain, and snow.</p>
        <ul>
          <li>Wind: &lt;25 low, 25–34 moderate, 35–44 high, 45–54 severe, ≥55 no travel.</li>
          <li>Rain in/hr: &lt;0.10, 0.10–0.25, 0.25–0.50, 0.50–1.00, &gt;1.00.</li>
          <li>Snow in/hr: &lt;0.5, 0.5–1.0, 1.0–2.0, 2.0–3.0, &gt;3.0.</li>
          <li>45–54 mph and a load over 30,000 lb becomes no travel.</li>
          <li>35–44 mph and a load over 40,000 lb becomes severe.</li>
        </ul>
        <p>The recommended route has the fewest no-travel miles, then fewest severe miles, then fewest high-risk miles, then the lowest distance-weighted average risk (low 1 through no travel 5), then the shortest travel time.</p>
      </details>
    </aside>
  );
}

function PlaceField({ label, name, placeholder }) {
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [open, setOpen] = useState(false);
  const [searchError, setSearchError] = useState("");
  const requestId = useRef(0);
  const wrapRef = useRef(null);

  useEffect(() => {
    function onDoc(event) {
      if (!wrapRef.current?.contains(event.target)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => {
    if (query.trim().length < 3 || query === picked?.label) {
      setSuggestions([]);
      setSearchError("");
      return undefined;
    }
    const current = ++requestId.current;
    const timer = setTimeout(async () => {
      try {
        const results = await searchPlaces(query.trim());
        if (current !== requestId.current) return;
        setSuggestions(results);
        setSearchError(results.length ? "" : "No matching places.");
        setOpen(true);
      } catch (err) {
        if (current !== requestId.current) return;
        setSuggestions([]);
        setSearchError(err.message);
        setOpen(true);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [query, picked]);

  return (
    <label className="place" ref={wrapRef}>
      {label}
      <input
        value={query}
        placeholder={placeholder}
        autoComplete="off"
        onChange={(event) => {
          setQuery(event.target.value);
          setPicked(null);
          setOpen(true);
        }}
        onFocus={() => suggestions.length && setOpen(true)}
        required
      />
      <input type="hidden" name={name} value={picked ? JSON.stringify(picked) : ""} />
      {open && (suggestions.length > 0 || searchError) && (
        <ul className="suggestions">
          {suggestions.map((place) => (
            <li key={`${place.lat},${place.lon},${place.label}`}>
              <button
                type="button"
                onClick={() => {
                  setPicked(place);
                  setQuery(place.label);
                  setOpen(false);
                  setSearchError("");
                }}
              >
                {place.label}
              </button>
            </li>
          ))}
          {!suggestions.length && searchError && <li className="hint">{searchError}</li>}
        </ul>
      )}
    </label>
  );
}

function RiskBar({ route }) {
  const parts = [
    ["low", route.low_miles],
    ["moderate", route.moderate_miles],
    ["high", route.high_miles],
    ["severe", route.severe_miles],
    ["no_travel", route.no_travel_miles],
  ];
  const total = parts.reduce((sum, [, miles]) => sum + miles, 0) || 1;
  return (
    <span className="stack" aria-hidden="true">
      {parts.map(([level, miles]) =>
        miles > 0 ? (
          <span
            key={level}
            style={{ width: `${(miles / total) * 100}%`, background: RISK_COLOR[level] }}
          />
        ) : null
      )}
    </span>
  );
}

function CheckpointList({ route, onCheckpoint }) {
  return (
    <div className="checks">
      {route.checkpoints.map((checkpoint) => (
        <button
          type="button"
          key={`${checkpoint.mile}`}
          className="check"
          onClick={() => onCheckpoint(checkpoint)}
        >
          <span className="check-main">
            <span className="mono">{checkpoint.mile.toFixed(0)} mi</span>
            <span>{formatWhen(checkpoint.eta)}</span>
            <span className={`pill ${checkpoint.level}`}>{RISK_LABEL[checkpoint.level]}</span>
          </span>
          <span className="check-wx">
            Wind {checkpoint.wind_mph} mph ({RISK_LABEL[checkpoint.wind_level]}) · Rain {checkpoint.rain_in_hr} in/hr · Snow{" "}
            {checkpoint.snow_in_hr} in/hr
          </span>
        </button>
      ))}
    </div>
  );
}
