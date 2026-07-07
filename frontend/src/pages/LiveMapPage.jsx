import React, { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { getLiveMapEvents } from "../api/client.js";

const LAYER_OPTIONS = [
  ["news", "News"],
  ["earthquakes", "Earthquakes"],
  ["disasters", "Disaster Alerts"],
  ["market", "Market-Relevant Events"],
];

const SEVERITY_WEIGHT = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

const SEVERITY_COLOR = {
  critical: "#ff3d5a",
  high: "#ff8b3d",
  medium: "#dfc07a",
  low: "#3ddc97",
};

function formatFreshness(minutes) {
  const value = Number(minutes || 0);
  if (value < 60) return `${value}m`;
  return `${Math.floor(value / 60)}h ${value % 60}m`;
}

function isEventInLayer(event, layer) {
  if (layer === "news") return event.type === "news";
  if (layer === "earthquakes") return event.type === "earthquake";
  if (layer === "disasters") return event.type === "disaster" || event.type === "security";
  if (layer === "market") return (event.related_assets || []).length > 0;
  return false;
}

function eventRadius(event) {
  const weight = SEVERITY_WEIGHT[event.severity] || 1;
  const marketBoost = (event.related_assets || []).length ? 2 : 0;
  return 7 + weight * 2 + marketBoost;
}

function EventFocus({ selectedEvent }) {
  const map = useMap();

  useEffect(() => {
    if (!selectedEvent) return;
    map.flyTo([selectedEvent.lat, selectedEvent.lon], 5, { duration: 0.7 });
  }, [map, selectedEvent]);

  return null;
}

function SourceHealth({ sources = [] }) {
  if (!sources.length) return null;

  return (
    <div className="source-health-row">
      {sources.map((source) => (
        <article className={source.ok ? "ok" : "down"} key={source.source}>
          <span>{source.source}</span>
          <strong>{source.ok ? "ONLINE" : "DEGRADED"}</strong>
          <small>
            {source.event_count} events - {source.latency_ms}ms
          </small>
        </article>
      ))}
    </div>
  );
}

function EventPopup({ event }) {
  return (
    <div className="map-popup">
      <div className="popup-topline">
        <span className={`severity-dot ${event.severity}`}>{event.severity}</span>
        <b>{event.source}</b>
      </div>
      <strong>{event.title}</strong>
      <p>{event.summary}</p>
      {!!event.related_assets?.length && (
        <div className="asset-badges compact">
          {event.related_assets.map((asset) => (
            <span key={asset}>{asset}</span>
          ))}
        </div>
      )}
      {event.url && (
        <a href={event.url} rel="noreferrer" target="_blank">
          Open source
        </a>
      )}
    </div>
  );
}

function AlertQueue({ events, selectedId, onSelect }) {
  if (!events.length) {
    return (
      <div className="map-empty">
        <span>No live events</span>
        <strong>Waiting for source data</strong>
        <small>Refresh the live map or check source health.</small>
      </div>
    );
  }

  return (
    <div className="alert-queue">
      {events.map((event) => (
        <button
          className={`alert-item ${event.severity} ${selectedId === event.id ? "active" : ""}`}
          key={`${event.source}-${event.id}`}
          onClick={() => onSelect(event)}
          type="button"
        >
          <span>
            <b>{event.type}</b>
            <em>{formatFreshness(event.freshness_minutes)}</em>
          </span>
          <strong>{event.title}</strong>
          <small>{event.source}{event.country ? ` - ${event.country}` : ""}</small>
          {!!event.related_assets?.length && (
            <div className="asset-badges">
              {event.related_assets.slice(0, 5).map((asset) => (
                <i key={asset}>{asset}</i>
              ))}
            </div>
          )}
        </button>
      ))}
    </div>
  );
}

export default function LiveMapPage() {
  const [events, setEvents] = useState([]);
  const [sourceHealth, setSourceHealth] = useState([]);
  const [activeLayers, setActiveLayers] = useState(["news", "earthquakes", "disasters", "market"]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadLiveMap(refresh = false) {
    setLoading(true);
    setError("");
    try {
      const payload = await getLiveMapEvents({ refresh, limit: 260 });
      setEvents(payload.events || []);
      setSourceHealth(payload.source_health || []);
      setSelectedEvent((payload.events || [])[0] || null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadLiveMap(false);
  }, []);

  const filteredEvents = useMemo(() => {
    const visible = events.filter((event) => activeLayers.some((layer) => isEventInLayer(event, layer)));
    return visible.sort(
      (a, b) =>
        (SEVERITY_WEIGHT[b.severity] || 0) - (SEVERITY_WEIGHT[a.severity] || 0) ||
        String(b.published_at).localeCompare(String(a.published_at))
    );
  }, [events, activeLayers]);

  function toggleLayer(layer) {
    setActiveLayers((current) => (current.includes(layer) ? current.filter((item) => item !== layer) : [...current, layer]));
  }

  return (
    <section className="live-map-page">
      <div className="map-command-panel panel-accent">
        <div>
          <p className="eyebrow">Live World Map</p>
          <h2>Global event radar</h2>
          <span>News, earthquakes, disaster alerts and market-sensitive vectors.</span>
        </div>
        <div className="map-actions">
          <strong>{filteredEvents.length}</strong>
          <span>visible events</span>
          <button onClick={() => loadLiveMap(true)} type="button">
            {loading ? "Loading" : "Refresh map"}
          </button>
        </div>
      </div>

      {error && <div className="error-box">{error}</div>}
      <SourceHealth sources={sourceHealth} />

      <div className="map-layer-bar">
        {LAYER_OPTIONS.map(([key, label]) => (
          <button className={activeLayers.includes(key) ? "active" : ""} key={key} onClick={() => toggleLayer(key)} type="button">
            {label}
          </button>
        ))}
      </div>

      <div className="live-map-grid">
        <section className="exchange-panel map-panel">
          <MapContainer center={[20, 0]} className="world-map" scrollWheelZoom zoom={2}>
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <EventFocus selectedEvent={selectedEvent} />
            {filteredEvents.map((event) => (
              <CircleMarker
                center={[event.lat, event.lon]}
                color={SEVERITY_COLOR[event.severity] || SEVERITY_COLOR.low}
                fillColor={SEVERITY_COLOR[event.severity] || SEVERITY_COLOR.low}
                fillOpacity={0.34}
                key={`${event.source}-${event.id}`}
                opacity={0.95}
                radius={eventRadius(event)}
                weight={2}
              >
                <Popup>
                  <EventPopup event={event} />
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        </section>

        <aside className="exchange-panel map-alert-panel">
          <div className="exchange-panel-head compact">
            <div>
              <p className="eyebrow">Alert Queue</p>
              <h2>Recent events</h2>
            </div>
          </div>
          <AlertQueue events={filteredEvents.slice(0, 80)} onSelect={setSelectedEvent} selectedId={selectedEvent?.id} />
        </aside>
      </div>
    </section>
  );
}
