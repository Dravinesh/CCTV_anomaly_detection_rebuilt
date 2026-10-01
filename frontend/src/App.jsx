import UploadPanel from "./components/UploadPanel";
import LiveFeedPanel from "./components/LiveFeedPanel";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>CCTV Anomaly Detection</h1>
      </header>
      <main className="app-grid">
        <UploadPanel />
        <LiveFeedPanel />
      </main>
    </div>
  );
}
