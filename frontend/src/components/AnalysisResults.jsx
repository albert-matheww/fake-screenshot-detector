import { ShieldCheckIcon, AlertTriangleIcon, DownloadIcon, RefreshIcon, LockIcon } from "../icons.jsx";

function pct(value) {
  return `${Math.round((value ?? 0) * 100)}%`;
}

function severityOf(score) {
  if (score >= 0.5) return "high";
  if (score >= 0.2) return "medium";
  return "low";
}

const METER_CLASS = { low: "good", medium: "warning", high: "critical" };

function Meter({ score }) {
  const level = severityOf(score ?? 0);
  return (
    <div className={`meter meter--${METER_CLASS[level]}`}>
      <div className="meter__fill" style={{ width: pct(score) }} />
    </div>
  );
}

function CueRow({ label, score, note }) {
  const level = severityOf(score ?? 0);
  return (
    <li className={`cue cue--${level}`}>
      <div className="cue__header">
        <span className="cue__label">{label}</span>
        <span className="cue__score">{pct(score)}</span>
      </div>
      <Meter score={score} />
      {note && <p className="cue__note">{note}</p>}
    </li>
  );
}

export default function AnalysisResults({ result, originalPreviewUrl, onReset }) {
  if (!result) return null;

  const { fake_score, verdict, ela_image, details, meta, override_reason } = result;
  const isFake = result.is_fake;
  const OVERRIDE_LABELS = { metadata_score: "Metadata / EXIF", text_score: "Document text (OCR)" };

  const cues = [
    {
      label: "Document text (OCR) — watermarks & placeholder data",
      score: details?.document_text?.score,
      note: details?.document_text?.matched_flags?.length
        ? details.document_text.matched_flags.join("; ")
        : (details?.document_text?.note ?? "No generator watermarks or placeholder data detected in the text."),
    },
    {
      label: "Error Level Analysis (ELA)",
      score: details?.ela?.score,
      note: `Largest anomalous cluster: ${details?.ela?.cluster_size ?? 0} block(s); hotspot ratio ${pct(details?.ela?.hotspot_ratio)}.`,
    },
    {
      label: "JPEG Ghost (double-compression) — informational, not scored",
      score: details?.jpeg_ghost?.score,
      note: details?.jpeg_ghost?.note
        ?? `Dominant quality ${details?.jpeg_ghost?.dominant_quality}; largest disagreeing cluster: ${details?.jpeg_ghost?.largest_cluster_size ?? 0} block(s). Excluded from fake_score — see README for why.`,
    },
    {
      label: "JPEG quantization tables",
      score: details?.quantization?.score,
      note: details?.quantization?.present
        ? `${details.quantization.num_tables} quantization table(s) found${details.quantization.suspicious_multiple_tables ? " — more than expected for a single compression." : "."}`
        : details?.quantization?.note,
    },
    {
      label: "Noise consistency",
      score: details?.noise?.score,
      note: details?.noise?.noise_cv != null
        ? `Block noise coefficient of variation: ${details.noise.noise_cv}`
        : details?.noise?.note,
    },
    {
      label: "Copy-move (clone) detection",
      score: details?.clone_detection?.score,
      note: `${details?.clone_detection?.dominant_offset_votes ?? 0} block(s) share a common displacement vector among ${details?.clone_detection?.textured_blocks ?? 0} textured blocks (source compactness ${pct(details?.clone_detection?.source_compactness)}).`,
    },
    {
      label: "Metadata / EXIF",
      score: details?.metadata?.score,
      note: details?.metadata?.suspicious_flags?.length
        ? details.metadata.suspicious_flags.join("; ")
        : "No suspicious metadata flags.",
    },
  ];

  const downloadReport = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "forensic-report.json";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="results">
      <div className={`verdict-card verdict-card--${isFake ? "fake" : "authentic"}`}>
        <div className="verdict-card__main">
          <div className="verdict-card__icon">
            {isFake ? <AlertTriangleIcon size={24} /> : <ShieldCheckIcon size={24} />}
          </div>
          <div className="verdict-card__body">
            <p className="verdict-card__label">{verdict}</p>
            <div className="verdict-card__score-row">
              <p className="verdict-card__score">Fake score: {pct(fake_score)}</p>
              <div className="verdict-card__meter">
                <Meter score={fake_score} />
              </div>
            </div>
            {override_reason && (
              <p className="verdict-card__override">
                <AlertTriangleIcon size={14} />
                Flagged by high-confidence override: {OVERRIDE_LABELS[override_reason] ?? override_reason}
                {" "}(composite score alone would not have crossed the threshold)
              </p>
            )}
          </div>
        </div>
        <div className="verdict-card__actions">
          <button className="button button--ghost" onClick={downloadReport}>
            <DownloadIcon size={16} />
            Report
          </button>
          {onReset && (
            <button className="button button--ghost" onClick={onReset}>
              <RefreshIcon size={16} />
              New scan
            </button>
          )}
        </div>
      </div>

      <div className="image-compare">
        <div className="image-compare__item">
          <p className="image-compare__title">Original</p>
          {originalPreviewUrl && <img src={originalPreviewUrl} alt="Uploaded screenshot" />}
        </div>
        <div className="image-compare__item">
          <p className="image-compare__title">ELA heatmap</p>
          {ela_image && <img src={ela_image} alt="Error level analysis heatmap" />}
        </div>
      </div>

      <div className="cues-section">
        <h3>Forensic cue breakdown</h3>
        <ul className="cues">
          {cues.map((cue) => (
            <CueRow key={cue.label} {...cue} />
          ))}
        </ul>
      </div>

      {meta && (
        <p className="meta-line">
          Model: {meta.model} · Processed in {meta.processing_ms} ms · SHA-256: {meta.sha256?.slice(0, 16)}…
        </p>
      )}

      <p className="disclaimer">
        <LockIcon size={15} />
        This is an automated heuristic analysis, not a certified forensic conclusion.
        Treat results as one input among several and use human review for
        high-stakes decisions.
      </p>
    </div>
  );
}
