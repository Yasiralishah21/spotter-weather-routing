import { useState } from "react";
import { analyzeTrip } from "./api";
import MapView from "./components/MapView";
import Sidebar from "./components/Sidebar";
import { defaultDepartureInput } from "./format";

export default function App() {
  const [departure, setDeparture] = useState(defaultDepartureInput);
  const [load, setLoad] = useState("35000");
  const [interval, setInterval] = useState("25");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);
  const [selectedId, setSelectedId] = useState("A");
  const [hour, setHour] = useState(0);
  const [focus, setFocus] = useState(null);

  async function onSubmit(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    let origin;
    let destination;
    try {
      origin = JSON.parse(form.get("origin") || "");
      destination = JSON.parse(form.get("destination") || "");
    } catch {
      origin = null;
      destination = null;
    }
    if (!origin?.label || !destination?.label) {
      setError("Choose an origin and a destination from the suggestions.");
      return;
    }
    const loadWeight = Number(load);
    if (!Number.isFinite(loadWeight) || loadWeight <= 0 || loadWeight > 250000) {
      setError("Enter a load weight between 1 and 250,000 lb.");
      return;
    }
    const when = new Date(departure);
    if (Number.isNaN(when.getTime())) {
      setError("Choose a departure date and time.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const next = await analyzeTrip({
        origin,
        destination,
        departure: when.toISOString(),
        load_weight_lb: loadWeight,
        interval_miles: Number(interval),
      });
      setResult(next);
      setSelectedId(next.routes[0]?.id || "A");
      setHour(0);
      setFocus(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <Sidebar
        departure={departure}
        setDeparture={setDeparture}
        load={load}
        setLoad={setLoad}
        interval={interval}
        setInterval={setInterval}
        loading={loading}
        error={error}
        result={result}
        selectedId={selectedId}
        onSelect={setSelectedId}
        onCheckpoint={setFocus}
        onSubmit={onSubmit}
      />
      <MapView
        result={result}
        selectedId={selectedId}
        onSelect={setSelectedId}
        hour={hour}
        onHour={setHour}
        focus={focus}
        loading={loading}
      />
    </div>
  );
}
