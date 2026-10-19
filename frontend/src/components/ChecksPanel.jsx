import { TYPE_STATUS_TEXT, CHECK_STATUS_TEXT } from "../lib/checks.js";

// Shows how the screenshot was routed and what each check did. A check that could not examine the
// screenshot says so and is never shown as a pass; an advisory check is shown but not counted.
export default function ChecksPanel({ routing, checks, coverage, verifySteps }) {
  if (!routing && (!checks || checks.length === 0)) return null;
  return (
    <section className="card" aria-labelledby="checks-heading" data-testid="checks-panel">
      <h3 id="checks-heading" className="card__title">How this screenshot was checked</h3>
      {routing && (
        <p className="routing" data-testid="routing">
          <strong>Type:</strong> {routing.label || "Unknown type"}{" "}
          <span className="muted">({TYPE_STATUS_TEXT[routing.status] || routing.status})</span>
          {routing.router_validated === false && (
            <span className="muted"> - the type router has not yet been validated on real screenshots, so type-specific checks are off.</span>
          )}
        </p>
      )}
      {coverage && (
        <p className="muted" data-testid="coverage">
          {coverage.live_clear} calibrated check(s) found nothing, {coverage.live_findings} found something,{" "}
          {coverage.advisory_findings} advisory signal(s) not counted, {coverage.not_applicable} could not examine this screenshot.
        </p>
      )}
      <ul className="checks">
        {checks.map((c) => {
          const counted = c.gate?.status === "live";
          return (
            <li key={c.id} className={`check check--${c.status}`} data-testid="check">
              <div className="check__head">
                <span className="check__name">{c.name}</span>
                <span className={`chip chip--check-${c.status}`}>{CHECK_STATUS_TEXT[c.status] || c.status}</span>
                <span className={`chip ${counted ? "chip--live" : "chip--advisory"}`}>
                  {counted ? "counts toward verdict" : c.gate?.uninformative ? "hint, not informative" : "advisory, not counted"}
                </span>
              </div>
              {c.why && <p className="muted check__why">{c.why}</p>}
              {c.status === "finding" && c.findings?.length > 0 && (
                <ul className="check__findings">
                  {c.findings.map((f, i) => (
                    <li key={i}>{f.message}</li>
                  ))}
                </ul>
              )}
              {!counted && c.gate?.reason && <p className="muted check__why">Why advisory: {c.gate.reason}</p>}
            </li>
          );
        })}
      </ul>
      {verifySteps?.length > 0 && (
        <>
          <h4 className="card__subtitle">What to do next</h4>
          <ol className="verify" data-testid="verify-steps">
            {verifySteps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ol>
        </>
      )}
    </section>
  );
}
