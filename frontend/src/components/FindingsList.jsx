import { SEVERITY_LABELS } from "../lib/result.js";

const SEVERITY_ORDER = { high: 0, medium: 1, low: 2 };

function formatValue(v) {
  if (v == null) return "-";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export default function FindingsList({ findings }) {
  const sorted = [...findings].sort((a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]);
  return (
    <section className="card" aria-labelledby="findings-heading">
      <h3 id="findings-heading" className="card__title">
        Rule checks {sorted.length > 0 && <span className="count">{sorted.length}</span>}
      </h3>
      {sorted.length === 0 ? (
        <p className="muted">No rule-based contradictions found.</p>
      ) : (
        <ul className="findings">
          {sorted.map((f, i) => {
            const entries = Object.entries(f.evidence);
            return (
              <li key={`${f.id}-${i}`} className={`finding finding--${f.severity}`} data-testid="finding">
                <div className="finding__head">
                  <span className={`chip chip--sev-${f.severity}`}>
                    {SEVERITY_LABELS[f.severity]}
                    <span className="sr-only"> severity</span>
                  </span>
                  <code className="finding__id">{f.id}</code>
                </div>
                <p className="finding__msg">{f.message}</p>
                {entries.length > 0 && (
                  <details className="finding__details">
                    <summary>Evidence</summary>
                    <dl>
                      {entries.map(([k, v]) => (
                        <div key={k}>
                          <dt>{k}</dt>
                          <dd>{formatValue(v)}</dd>
                        </div>
                      ))}
                    </dl>
                  </details>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
