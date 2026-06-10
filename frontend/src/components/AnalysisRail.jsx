function confTier(c) {
  if (c >= 90) return "hi";
  if (c >= 70) return "mid";
  return "lo";
}

function Confidence({ value }) {
  return (
    <span className={"conf conf-" + confTier(value) + " mono"}>
      {Math.round(value)}%
    </span>
  );
}

function checkLabel(check, field) {
  const stripped = field.replace(/^mrz_/, "").replace(/_/g, " ");
  switch (check) {
    case "verhoeff_checksum": return "Verhoeff checksum";
    case "format": return field.replace(/_/g, " ") + " format";
    case "date_validity": return "Date-of-birth validity";
    case "check_digit": return "MRZ " + stripped + " check digit";
    case "mrz_vs_printed": return "MRZ vs printed DOB";
    default: return check.replace(/_/g, " ");
  }
}

function Verification({ verification }) {
  const checks = verification.checks || [];
  if (checks.length === 0) {
    return (
      <section className="rail-block">
        <span className="eyebrow">Verification</span>
        <p className="muted-note">No checks available for this document.</p>
      </section>
    );
  }
  const failed = checks.filter((c) => !c.passed).length;

  return (
    <section className="rail-block">
      <span className="eyebrow">Verification</span>
      <div className={"verdict " + (verification.is_valid ? "verdict-ok" : "verdict-bad")}>
        <span className="verdict-mark">{verification.is_valid ? "✓" : "✕"}</span>
        <span>
          {verification.is_valid
            ? "All checks passed"
            : failed + " of " + checks.length + " checks failed"}
        </span>
      </div>
      <ul className="check-list">
        {checks.map((c, i) => (
          <li key={i} className={"check " + (c.passed ? "check-ok" : "check-bad")}>
            <span className="check-mark">{c.passed ? "✓" : "✕"}</span>
            <div className="check-body">
              <span className="check-name">{checkLabel(c.check, c.field)}</span>
              <span className="check-detail">{c.detail}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

export default function AnalysisRail({ result, status, error, onHoverField }) {
  const hover = onHoverField || (() => {});

  if (status === "idle") {
    return (
      <aside className="rail">
        <div className="rail-empty">
          <p>Upload a document to read its type, fields, and verification.</p>
        </div>
      </aside>
    );
  }

  if (status === "reading") {
    return (
      <aside className="rail">
        <div className="rail-empty"><p className="pulse">Reading…</p></div>
      </aside>
    );
  }

  if (status === "error") {
    return (
      <aside className="rail">
        <div className="rail-error">
          <h2>Couldn't read that file</h2>
          <p>{error}</p>
        </div>
      </aside>
    );
  }

  if (!result) return <aside className="rail" />;

  const { analysis, metadata, text } = result;
  const isUnknown = analysis.document_type === "unknown";

  return (
    <aside className="rail">
      <div className="rail-head">
        <span className="eyebrow">Detected type</span>
        <div className="type-row">
          <h2 className="doc-type">{analysis.document_type.toUpperCase()}</h2>
          <Confidence value={analysis.type_confidence} />
        </div>
        {metadata.from_cache && <span className="cache-flash">Served from cache</span>}
      </div>

      {isUnknown ? (
        <div className="unknown-note">
          <p>
            This doesn't match a known identity document (Aadhaar, PAN, or
            passport), so fields and verification are skipped.
          </p>
        </div>
      ) : (
        <>
          <Verification verification={analysis.verification} />

          <section className="rail-block">
            <span className="eyebrow">Fields</span>
            {analysis.fields.length === 0 ? (
              <p className="muted-note">No fields extracted.</p>
            ) : (
              <ul className="field-list">
                {analysis.fields.map((f) => (
                  <li
                    key={f.name}
                    className={"field" + (f.boxes && f.boxes.length ? " field-locatable" : "")}
                    onMouseEnter={() => hover(f.boxes || null)}
                    onMouseLeave={() => hover(null)}
                  >
                    <span className="field-label">{f.name.replace(/_/g, " ")}</span>
                    <Confidence value={f.confidence} />
                    <span className="field-value mono">{f.value}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}

      <section className="rail-block">
        <span className="eyebrow">Run</span>
        <dl className="meta">
          <div><dt>Engine</dt><dd className="mono">{metadata.engine}</dd></div>
          <div><dt>Pages</dt><dd className="mono">{metadata.page_count}</dd></div>
          <div><dt>Time</dt><dd className="mono">{metadata.processing_time_ms} ms</dd></div>
        </dl>
      </section>

      <section className="rail-block">
        <span className="eyebrow">Extracted text</span>
        <pre className="text-dump mono">{text || "—"}</pre>
      </section>
    </aside>
  );
}
