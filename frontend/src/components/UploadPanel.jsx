import { useState } from "react";
import ScoreChart from "./ScoreChart";

function span(clip) {
  return clip.start_sec != null ? `${clip.start_sec}s - ${clip.end_sec}s` : `frames ${clip.start_frame}-${clip.end_frame}`;
}

export default function UploadPanel() {
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  function pick(e) {
    setFile(e.target.files?.[0] || null);
    setResult(null);
    setError("");
  }

  async function analyze() {
    if (!file) return;
    setLoading(true);
    setResult(null);
    setError("");
    try {
      const form = new FormData();
      form.append("video", file);
      const res = await fetch("/api/analyze-video", { method: "POST", body: form });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
      setResult(data);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  const peak = result ? result.clips[result.peak_clip] : null;

  return (
    <section className="panel">
      <h2>Upload a video</h2>
      <div className="upload-row">
        <input type="file" accept="video/*" onChange={pick} disabled={loading} />
        <button type="button" onClick={analyze} disabled={!file || loading}>
          {loading ? "Analyzing..." : "Analyze"}
        </button>
      </div>

      {loading && <p className="muted">Analyzing {file?.name} - this can take a while for long videos.</p>}
      {error && <p className="error">{error}</p>}

      {result && (
        <div className="result">
          <div className={`verdict ${result.is_anomaly ? "verdict-anomaly" : "verdict-normal"}`}>
            {result.is_anomaly ? "Anomaly detected" : "No anomaly detected"}
          </div>
          <dl className="stats">
            <div>
              <dt>Peak score</dt>
              <dd>{result.score.toFixed(3)}</dd>
            </div>
            <div>
              <dt>Threshold</dt>
              <dd>{result.threshold}</dd>
            </div>
            <div>
              <dt>Clips scored</dt>
              <dd>{result.num_clips}</dd>
            </div>
            {result.is_anomaly && peak && (
              <div>
                <dt>Peak at</dt>
                <dd>{span(peak)}</dd>
              </div>
            )}
          </dl>
          <h3>Score per clip</h3>
          <ScoreChart clips={result.clips} threshold={result.threshold} />
          <p className="muted">Dashed line = threshold. Clips are evenly sampled across the video.</p>
        </div>
      )}
    </section>
  );
}
