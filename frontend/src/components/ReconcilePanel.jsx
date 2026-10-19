import { useEffect, useMemo, useState } from "react";
import TypePicker from "./TypePicker.jsx";
import AssurancePanel from "./AssurancePanel.jsx";
import AnalysisResults from "./AnalysisResults.jsx";
import { reconcileImages, toApiError } from "../services/api.js";
import { normalizeAssurance } from "../lib/result.js";
import { FIELD_KIND_LABELS, FIELD_STATUS_TEXT, RECONCILE_STATUS_TEXT } from "../lib/checks.js";

const fmt = (kind, v) => (kind === "amounts" ? Number(v).toLocaleString("en-IN", { minimumFractionDigits: 2 }) : String(v));

// Reconcile mode: check the screenshot against a second source the sender did not supply.
export default function ReconcilePanel() {
  const [image, setImage] = useState(null);
  const [type, setType] = useState("auto");
  const [sourceText, setSourceText] = useState("");
  const [sourceImage, setSourceImage] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const url = useMemo(() => (image ? URL.createObjectURL(image) : null), [image]);
  useEffect(() => () => url && URL.revokeObjectURL(url), [url]);

  const ready = image && (sourceText.trim() || sourceImage) && !loading;
  const run = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await reconcileImages(image, { type, sourceText: sourceText.trim(), sourceImage }));
    } catch (err) {
      setError(toApiError(err));
    } finally {
      setLoading(false);
    }
  };
  const rec = result?.reconcile;

  return (
    <section className="card reconcile" aria-labelledby="reconcile-heading" data-testid="reconcile-panel">
      <h2 id="reconcile-heading" className="card__title">Check against a second source</h2>
      <p className="muted">
        A forged screenshot can agree with itself, but it cannot change another record. Add something you did <strong>not</strong> get
        from the sender: the receiver&apos;s bank SMS, a statement line, or the issuer&apos;s e-mail. Every amount, date and reference in it
        is looked up in the screenshot.
      </p>
      <div className="compare__field">
        <label htmlFor="rec-shot">Screenshot to check</label>
        <input id="rec-shot" type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setImage(e.target.files?.[0] || null)} />
      </div>
      <TypePicker id="rec-type" value={type} onChange={setType} disabled={loading} />
      <div className="compare__field">
        <label htmlFor="rec-text">Second source, as text (paste the SMS or statement line)</label>
        <textarea id="rec-text" rows={4} value={sourceText} onChange={(e) => setSourceText(e.target.value)} placeholder="Rs.2,500.00 debited on 12-10-2026 ... UPI Ref No 628512345678" />
      </div>
      <div className="compare__field">
        <label htmlFor="rec-img">or as an image (a screenshot of that record)</label>
        <input id="rec-img" type="file" accept="image/png,image/jpeg,image/webp" onChange={(e) => setSourceImage(e.target.files?.[0] || null)} />
      </div>
      <button type="button" className="button" onClick={run} disabled={!ready}>{loading ? "Checking..." : "Check against the second source"}</button>
      {error && <p role="alert" className="compare__error">{error.message}</p>}

      {result && (
        <div className="reconcile__result" data-testid="reconcile-result">
          <AssurancePanel assurance={normalizeAssurance(result.assurance)} />
          {rec && (
            <section className="card" aria-labelledby="facts-heading">
              <h3 id="facts-heading" className="card__title">Facts compared</h3>
              <p data-testid="reconcile-status"><strong>{RECONCILE_STATUS_TEXT[rec.status] || rec.status}</strong></p>
              {rec.rows?.length > 0 && (
                <table className="compare__table" data-testid="facts-table">
                  <thead><tr><th>Fact</th><th>Second source</th><th>Screenshot</th><th>Result</th></tr></thead>
                  <tbody>
                    {rec.rows.filter((r) => r.status !== "not_in_source").map((r) => (
                      <tr key={r.kind} className={`fact fact--${r.status}`}>
                        <td>{FIELD_KIND_LABELS[r.kind] || r.kind}</td>
                        <td>{r.source.map((v) => fmt(r.kind, r.kind === "times" ? `${String(Math.floor(v / 60)).padStart(2, "0")}:${String(v % 60).padStart(2, "0")}` : v)).join(", ") || "-"}</td>
                        <td>{(r.screenshot || []).slice(0, 4).map((v) => fmt(r.kind, r.kind === "times" ? `${String(Math.floor(v / 60)).padStart(2, "0")}:${String(v % 60).padStart(2, "0")}` : v)).join(", ") || "-"}</td>
                        <td>{FIELD_STATUS_TEXT[r.status] || r.status}{r.note ? ` - ${r.note}` : ""}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <p className="muted">The screenshot&apos;s text is read twice; a mismatch is only called a conflict when both reads agree on a different value.</p>
            </section>
          )}
          <AnalysisResults result={result} imageUrl={url} onReset={() => setResult(null)} />
        </div>
      )}
    </section>
  );
}
