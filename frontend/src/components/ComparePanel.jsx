import { useEffect, useMemo, useState } from "react";
import AnnotatedImage from "./AnnotatedImage.jsx";
import { compareImages, toApiError } from "../services/api.js";

function FileField({ id, label, file, onChange }) {
  return (
    <div className="compare__field">
      <label htmlFor={id}>{label}</label>
      <input id={id} type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => onChange(e.target.files?.[0] || null)} />
      {file && <span className="muted">{file.name}</span>}
    </div>
  );
}

// Compare mode: when the person has a genuine copy, show exactly what differs.
export default function ComparePanel() {
  const [original, setOriginal] = useState(null);
  const [suspect, setSuspect] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const suspectUrl = useMemo(() => (suspect ? URL.createObjectURL(suspect) : null), [suspect]);
  useEffect(() => () => suspectUrl && URL.revokeObjectURL(suspectUrl), [suspectUrl]);

  const run = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await compareImages(original, suspect));
    } catch (err) {
      setError(toApiError(err));
    } finally {
      setLoading(false);
    }
  };

  const regions = (result?.regions || []).map((r) => ({
    x: r.x, y: r.y, w: r.w, h: r.h, text: r.text || "", score: 1, source: "model", level: "evidence", reasons: r.reasons || [],
  }));

  return (
    <section className="card compare" aria-labelledby="compare-heading" data-testid="compare-panel">
      <h2 id="compare-heading" className="card__title">Compare with a genuine copy</h2>
      <p className="muted">
        If you hold the original screenshot (or a fresh capture of the same page), upload both. Every difference is marked.
        This needs no model and also finds edits that match the original font.
      </p>
      <FileField id="orig" label="Original (known genuine)" file={original} onChange={setOriginal} />
      <FileField id="susp" label="Suspect screenshot" file={suspect} onChange={setSuspect} />
      <button type="button" className="button" onClick={run} disabled={!original || !suspect || loading}>
        {loading ? "Comparing..." : "Compare"}
      </button>
      {error && <p role="alert" className="compare__error">{error.message}</p>}
      {result && (
        <div className="compare__result" data-testid="compare-result">
          <p><strong>{result.status === "differences_found" ? "Differences found" : result.status === "no_difference" ? "No difference found" : "Cannot compare"}</strong></p>
          <p className="muted">{result.message}</p>
          {result.caution && <p className="muted">{result.caution}</p>}
          {result.status === "differences_found" && suspectUrl && (
            <AnnotatedImage imageUrl={suspectUrl} image={result.image} regions={regions} activeIndex={null} selectedIndex={null} onHover={() => {}} onSelect={() => {}} />
          )}
          {result.text_changes?.length > 0 && (
            <table className="compare__table">
              <thead><tr><th>Change</th><th>Original</th><th>Suspect</th></tr></thead>
              <tbody>
                {result.text_changes.map((c, i) => (
                  <tr key={i}><td>{c.type}</td><td>{c.original || "-"}</td><td>{c.suspect || "-"}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  );
}
