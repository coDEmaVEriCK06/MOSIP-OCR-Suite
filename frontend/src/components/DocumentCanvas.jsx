import { useState } from "react";

function confTier(c) {
  if (c >= 90) return "hi";
  if (c >= 70) return "mid";
  return "lo";
}

export default function DocumentCanvas({ upload, words, highlight, status, onPick }) {
  const [dims, setDims] = useState(null);
  const [showBoxes, setShowBoxes] = useState(true);

  if (!upload) {
    return (
      <section className="canvas">
        <button className="dropzone" onClick={onPick}>
          <span className="dropzone-icon" aria-hidden="true" />
          <span className="dropzone-title">Drop an identity document here</span>
          <span className="dropzone-hint">PNG, JPG, or PDF · or click to browse</span>
        </button>
      </section>
    );
  }

  const pageWords = (words || []).filter((w) => w.page === 1);
  const ready = status === "done" && dims && !upload.isPdf && pageWords.length > 0;
  const hl = ready && highlight ? highlight : [];

  const pct = (b) => ({
    left: (b.x / dims.w) * 100 + "%",
    top: (b.y / dims.h) * 100 + "%",
    width: (b.width / dims.w) * 100 + "%",
    height: (b.height / dims.h) * 100 + "%",
  });

  return (
    <section className="canvas">
      <div className={"canvas-stage" + (status === "reading" ? " is-reading" : "")}>
        {upload.isPdf ? (
          <div className="pdf-placeholder">
            <span className="pdf-badge">PDF</span>
            <p>Page preview arrives with the multi-page viewer. Extraction runs on every page.</p>
          </div>
        ) : (
          <>
            <img
              key={upload.url}
              className="doc-image"
              src={upload.url}
              alt="Uploaded document"
              onLoad={(e) =>
                setDims({ w: e.target.naturalWidth, h: e.target.naturalHeight })
              }
            />
            {ready && showBoxes && (
              <div className="box-layer">
                {pageWords.map((w, i) => (
                  <span
                    key={i}
                    className={"box box-" + confTier(w.confidence)}
                    style={pct(w.bbox)}
                  >
                    <span className="box-label">
                      {w.text} · {Math.round(w.confidence)}%
                    </span>
                  </span>
                ))}
              </div>
            )}
            {hl.length > 0 && (
              <div className="box-layer">
                {hl.map((b, i) => (
                  <span key={i} className="box-hl" style={pct(b)} />
                ))}
              </div>
            )}
          </>
        )}

        {status === "reading" && (
          <div className="scan-veil"><span>Reading document…</span></div>
        )}

        {ready && (
          <button className="box-toggle" onClick={() => setShowBoxes((s) => !s)}>
            {showBoxes ? "Hide boxes" : "Show boxes"}
          </button>
        )}
      </div>
    </section>
  );
}
