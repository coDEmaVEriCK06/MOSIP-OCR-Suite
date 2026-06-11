import { useState } from "react";

function confTier(c) {
  if (c >= 90) return "hi";
  if (c >= 70) return "mid";
  return "lo";
}

const key = (b) => `${b.x},${b.y},${b.width},${b.height}`;

export default function DocumentCanvas({ upload, words, pages, highlight, status, onPick }) {
  const [dims, setDims] = useState(null);
  const [showBoxes, setShowBoxes] = useState(true);
  const [page, setPage] = useState(0);

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

  const isPdf = upload.isPdf;
  const pdfPages = isPdf ? pages || [] : [];
  const hasPdfPages = isPdf && pdfPages.length > 0;
  const src = isPdf ? (hasPdfPages ? pdfPages[page] : null) : upload.url;
  const pageNum = isPdf ? page + 1 : 1;

  if (isPdf && !hasPdfPages) {
    return (
      <section className="canvas">
        <div className="canvas-stage">
          <div className="pdf-placeholder">
            <span className="pdf-badge">PDF</span>
            <p>{status === "reading" ? "Reading every page…" : "No preview available."}</p>
          </div>
          {status === "reading" && (
            <div className="scan-veil"><span>Reading document…</span></div>
          )}
        </div>
      </section>
    );
  }

  const pageWords = (words || []).filter((w) => w.page === pageNum);
  const ready = status === "done" && dims && src;
  const onPageBox = new Set(pageWords.map((w) => key(w.bbox)));
  const hl = ready && highlight ? highlight.filter((b) => onPageBox.has(key(b))) : [];

  const pct = (b) => ({
    left: (b.x / dims.w) * 100 + "%",
    top: (b.y / dims.h) * 100 + "%",
    width: (b.width / dims.w) * 100 + "%",
    height: (b.height / dims.h) * 100 + "%",
  });

  return (
    <section className="canvas">
      <div className={"canvas-stage" + (status === "reading" ? " is-reading" : "")}>
        <img
          key={src}
          className="doc-image"
          src={src}
          alt={isPdf ? "Page " + pageNum : "Uploaded document"}
          onLoad={(e) => setDims({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
        />

        {ready && showBoxes && pageWords.length > 0 && (
          <div className="box-layer">
            {pageWords.map((w, i) => (
              <span key={i} className={"box box-" + confTier(w.confidence)} style={pct(w.bbox)}>
                <span className="box-label">{w.text} · {Math.round(w.confidence)}%</span>
              </span>
            ))}
          </div>
        )}

        {hl.length > 0 && (
          <div className="box-layer">
            {hl.map((b, i) => <span key={i} className="box-hl" style={pct(b)} />)}
          </div>
        )}

        {status === "reading" && (
          <div className="scan-veil"><span>Reading document…</span></div>
        )}

        {ready && pageWords.length > 0 && (
          <button className="box-toggle" onClick={() => setShowBoxes((s) => !s)}>
            {showBoxes ? "Hide boxes" : "Show boxes"}
          </button>
        )}

        {hasPdfPages && pdfPages.length > 1 && (
          <div className="pager">
            <button onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>‹</button>
            <span className="pager-label mono">Page {pageNum} / {pdfPages.length}</span>
            <button
              onClick={() => setPage((p) => Math.min(pdfPages.length - 1, p + 1))}
              disabled={page === pdfPages.length - 1}
            >›</button>
          </div>
        )}
      </div>
    </section>
  );
}
