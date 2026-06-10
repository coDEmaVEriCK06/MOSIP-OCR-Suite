import { useState, useCallback, useRef } from "react";
import { extractDocument } from "./api";
import DocumentCanvas from "./components/DocumentCanvas";
import AnalysisRail from "./components/AnalysisRail";

const ACCEPTED = ["image/png", "image/jpeg", "image/jpg", "application/pdf"];

export default function App() {
  const [upload, setUpload] = useState(null);
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);
  const [hovered, setHovered] = useState(null);
  const inputRef = useRef(null);

  const handleFile = useCallback(async (file) => {
    if (!file) return;
    setError(null);
    setResult(null);
    setHovered(null);
    setUpload({ url: URL.createObjectURL(file), isPdf: file.type === "application/pdf" });
    setStatus("reading");
    try {
      const data = await extractDocument(file);
      setResult(data);
      setStatus("done");
    } catch (e) {
      setError(e.message);
      setStatus("error");
    }
  }, []);

  const pick = () => inputRef.current?.click();

  const exportJson = () => {
    if (!result) return;
    const { pages, ...data } = result;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "extraction.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="app">
      <header className="appbar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true" />
          <div className="brand-text">
            <h1>Document Inspector</h1>
            <p>Identity-document extraction &amp; verification</p>
          </div>
        </div>
        <div className="appbar-actions">
          {status === "done" && (
            <button className="btn-ghost" onClick={exportJson}>Export JSON</button>
          )}
          <button className="btn-primary" onClick={pick}>Upload document</button>
          <input
            ref={inputRef}
            type="file"
            accept={ACCEPTED.join(",")}
            onChange={(e) => handleFile(e.target.files?.[0])}
            hidden
          />
        </div>
      </header>

      <main
        className="console"
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); handleFile(e.dataTransfer.files?.[0]); }}
      >
        <DocumentCanvas
          upload={upload}
          words={result?.words}
          pages={result?.pages}
          highlight={hovered}
          status={status}
          onPick={pick}
        />
        <AnalysisRail
          result={result}
          status={status}
          error={error}
          onHoverField={setHovered}
        />
      </main>
    </div>
  );
}
