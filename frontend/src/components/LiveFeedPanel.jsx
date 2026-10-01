import { useEffect, useRef, useState } from "react";

const MAX_EVENTS = 50;

export default function LiveFeedPanel() {
  const [frameUrl, setFrameUrl] = useState(null);
  const [connected, setConnected] = useState(false);
  const [camera, setCamera] = useState(null);
  const [status, setStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const frameUrlRef = useRef(null);

  useEffect(() => {
    let ws;
    let retryTimer;
    let closed = false;

    function setFrame(url) {
      if (frameUrlRef.current) URL.revokeObjectURL(frameUrlRef.current);
      frameUrlRef.current = url;
      setFrameUrl(url);
    }

    function connect() {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      ws = new WebSocket(`${protocol}://${window.location.host}/ws/live-feed`);
      ws.binaryType = "blob";

      ws.onopen = () => setConnected(true);
      ws.onclose = () => {
        setConnected(false);
        if (!closed) retryTimer = setTimeout(connect, 2000);
      };
      ws.onerror = () => ws.close();
      ws.onmessage = (event) => {
        if (typeof event.data !== "string") {
          setFrame(URL.createObjectURL(event.data));
          return;
        }
        let payload;
        try {
          payload = JSON.parse(event.data);
        } catch {
          return;
        }
        if (payload.type === "stream_started") {
          setCamera(payload.camera_name);
          setStatus(null);
        } else if (payload.type === "stream_ended") {
          setCamera(null);
          setStatus(null);
          setFrame(null);
        } else if (payload.type === "analysis") {
          setCamera(payload.camera_name);
          setStatus(payload);
          if (payload.new_anomaly) {
            setEvents((prev) => [payload, ...prev].slice(0, MAX_EVENTS));
          }
        }
      };
    }

    connect();
    return () => {
      closed = true;
      clearTimeout(retryTimer);
      ws?.close();
      if (frameUrlRef.current) URL.revokeObjectURL(frameUrlRef.current);
    };
  }, []);

  const anomaly = status?.is_anomaly;

  return (
    <section className="panel">
      <h2>
        Live feed
        <span className={`dot ${connected ? "dot-on" : "dot-off"}`} title={connected ? "Connected to backend" : "Disconnected"} />
      </h2>

      <div className={`live-frame-wrap ${anomaly ? "live-anomaly" : ""}`}>
        {frameUrl ? (
          <img src={frameUrl} alt="Live feed" className="live-frame" />
        ) : (
          <div className="empty">Waiting for a camera to connect...</div>
        )}
        {frameUrl && (
          <div className={`live-badge ${status ? (anomaly ? "badge-anomaly" : "badge-normal") : "badge-pending"}`}>
            {status ? (anomaly ? "ANOMALY" : "Normal") : "Analyzing..."}
            {status && <span className="badge-score">{status.score.toFixed(2)}</span>}
          </div>
        )}
      </div>
      {camera && <p className="muted">Camera: {camera}</p>}

      <h3>Detected anomalies</h3>
      {events.length === 0 ? (
        <p className="muted">None yet.</p>
      ) : (
        <ul className="event-list">
          {events.map((e, i) => (
            <li key={`${e.timestamp}-${i}`}>
              <span className="event-time">{new Date(e.timestamp).toLocaleTimeString()}</span>
              <span>{e.camera_name}</span>
              <span className="event-score">score {e.score.toFixed(2)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
