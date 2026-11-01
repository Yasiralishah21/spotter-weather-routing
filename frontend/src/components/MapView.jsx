import { useEffect, useRef } from "react";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, useMap } from "react-leaflet";
import L from "leaflet";
import {
  RISK_COLOR,
  RISK_LABEL,
  ROUTE_COLOR,
  addHours,
  formatDuration,
  formatWhen,
} from "../format";

const LEGEND = [
  ["L", "Low"],
  ["M", "Moderate"],
  ["H", "High"],
  ["S", "Severe"],
  ["N", "No travel"],
];

export default function MapView({ result, selectedId, onSelect, hour, onHour, focus, loading }) {
  const routes = result?.routes ?? [];
  const selected = routes.find((route) => route.id === selectedId) ?? routes[0];
  const ordered = [...routes].sort((a, b) => Number(a.id === selected?.id) - Number(b.id === selected?.id));
  const forecastTime = result ? formatWhen(addHours(result.departure, hour).toISOString()) : "";

  return (
    <div className="map-wrap">
      <MapContainer center={[39.5, -96.5]} zoom={4} scrollWheelZoom>
        <TileLayer
          attribution="&copy; OpenStreetMap"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <InvalidateSize />
        {routes.length > 0 && <FitToRoutes routes={routes} />}
        {focus && <FlyTo checkpoint={focus} />}
        {ordered.map((route) => (
          <RouteLine
            key={route.id}
            route={route}
            selected={route.id === selected?.id}
            onSelect={onSelect}
          />
        ))}
        {selected?.checkpoints.map((checkpoint) => (
          <CircleMarker
            key={`${selected.id}-${checkpoint.mile}`}
            center={[checkpoint.lat, checkpoint.lon]}
            radius={7}
            pathOptions={{
              color: "#ffffff",
              weight: 2,
              fillColor: RISK_COLOR[checkpoint.level],
              fillOpacity: 1,
            }}
          >
            <Popup>
              <strong>
                {checkpoint.mile.toFixed(0)} mi · {RISK_LABEL[checkpoint.level]}
              </strong>
              <br />
              ETA {formatWhen(checkpoint.eta)}
              <br />
              Wind {checkpoint.wind_mph} mph ({RISK_LABEL[checkpoint.wind_level]})
              <br />
              Rain {checkpoint.rain_in_hr} in/hr ({RISK_LABEL[checkpoint.rain_level]})
              <br />
              Snow {checkpoint.snow_in_hr} in/hr ({RISK_LABEL[checkpoint.snow_level]})
            </Popup>
          </CircleMarker>
        ))}
        {result && (
          <>
            <PlaceDot place={result.origin} kind="origin" />
            <PlaceDot place={result.destination} kind="destination" />
          </>
        )}
        {selected && (
          <HeatDots points={selected.heatmap} hour={hour} departure={result.departure} />
        )}
      </MapContainer>

      {!result && !loading && (
        <div className="map-chip">Routes, checkpoints, and the weather corridor show up here.</div>
      )}
      {loading && <div className="map-chip">Reading driving routes and the hourly forecast…</div>}

      {result && selected && (
        <section className="forecast">
          <div className="forecast-top">
            <strong>{selected.name} corridor</strong>
            <span className="mono">
              +{hour}h · {forecastTime}
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="48"
            step="1"
            value={hour}
            aria-label="Hours after departure"
            onChange={(event) => onHour(Number(event.target.value))}
          />
          <div className="scale">
            <span>Departure</span>
            <span>+24h</span>
            <span>+48h</span>
          </div>
          <div className="legend">
            {LEGEND.map(([code, label]) => (
              <span key={code}>
                <i style={{ background: RISK_COLOR[code] }} />
                {label}
              </span>
            ))}
          </div>
          <p>
            Same risk rules as the checkpoints, drawn 8 miles either side of the selected road.
            Drag to move the forecast. Gray means that hour is outside the forecast.
          </p>
        </section>
      )}
    </div>
  );
}

function RouteLine({ route, selected, onSelect }) {
  const color = ROUTE_COLOR[route.id];
  return (
    <>
      {selected && (
        <Polyline positions={route.geometry} pathOptions={{ color: "#ffffff", weight: 11, opacity: 0.95 }} />
      )}
      <Polyline
        positions={route.geometry}
        pathOptions={{ color, weight: selected ? 6 : 4, opacity: selected ? 0.95 : 0.62 }}
        eventHandlers={{ click: () => onSelect(route.id) }}
      >
        <Popup>
          <strong>
            {route.name}
            {route.recommended ? " · Recommended" : ""}
          </strong>
          <br />
          {route.distance_miles.toFixed(1)} mi · {formatDuration(route.duration_seconds)}
          <br />
          Severe {route.severe_miles.toFixed(1)} mi · High {route.high_miles.toFixed(1)} mi
          <br />
          No travel {route.no_travel_miles.toFixed(1)} mi · Avg risk {route.average_risk.toFixed(2)}
          {route.reason ? (
            <>
              <br />
              {route.reason}
            </>
          ) : null}
        </Popup>
      </Polyline>
    </>
  );
}

function PlaceDot({ place, kind }) {
  return (
    <CircleMarker
      center={[place.lat, place.lon]}
      radius={8}
      pathOptions={{
        color: "#17202b",
        weight: 2,
        fillColor: kind === "origin" ? "#f4f7fb" : "#f0b429",
        fillOpacity: 1,
      }}
    >
      <Popup>
        <strong>{kind === "origin" ? "Origin" : "Destination"}</strong>
        <br />
        {place.label}
      </Popup>
    </CircleMarker>
  );
}

function HeatDots({ points, hour, departure }) {
  const map = useMap();
  const hourRef = useRef(hour);
  const departureRef = useRef(departure);
  const markersRef = useRef([]);
  hourRef.current = hour;
  departureRef.current = departure;

  useEffect(() => {
    if (!map.getPane("heat")) {
      const pane = map.createPane("heat");
      pane.style.zIndex = "350";
    }
    const group = L.layerGroup().addTo(map);
    const markers = points.map((point) => {
      const code = point.levels[hourRef.current] || "X";
      const marker = L.circleMarker([point.lat, point.lon], {
        pane: "heat",
        radius: 10,
        stroke: false,
        fillOpacity: 0.5,
        fillColor: RISK_COLOR[code] || RISK_COLOR.X,
      });
      marker.on("mouseover", () => {
        const currentHour = hourRef.current;
        const level = point.levels[currentHour] || "X";
        const when = formatWhen(addHours(departureRef.current, currentHour).toISOString());
        marker.unbindTooltip();
        marker.bindTooltip(`${RISK_LABEL[level]} · ${when}`, { sticky: true, opacity: 0.96 });
        marker.openTooltip();
      });
      marker.addTo(group);
      return marker;
    });
    markersRef.current = markers;
    return () => {
      group.remove();
      markersRef.current = [];
    };
  }, [map, points]);

  useEffect(() => {
    markersRef.current.forEach((marker, index) => {
      const code = points[index]?.levels?.[hour] || "X";
      marker.setStyle({ fillColor: RISK_COLOR[code] || RISK_COLOR.X });
    });
  }, [hour, points]);

  return null;
}

function FitToRoutes({ routes }) {
  const map = useMap();
  const signature = routes.map((route) => `${route.id}:${route.distance_miles}`).join("|");
  useEffect(() => {
    const positions = routes.flatMap((route) => route.geometry);
    if (positions.length) map.fitBounds(positions, { padding: [42, 42] });
  }, [map, signature, routes]);
  return null;
}

function FlyTo({ checkpoint }) {
  const map = useMap();
  useEffect(() => {
    map.panTo([checkpoint.lat, checkpoint.lon], { animate: true });
  }, [map, checkpoint]);
  return null;
}

function InvalidateSize() {
  const map = useMap();
  useEffect(() => {
    const fix = () => map.invalidateSize();
    const timer = setTimeout(fix, 150);
    window.addEventListener("resize", fix);
    return () => {
      clearTimeout(timer);
      window.removeEventListener("resize", fix);
    };
  }, [map]);
  return null;
}
