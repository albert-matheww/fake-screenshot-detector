// How much independent evidence supports this screenshot. It never says "genuine": level 1 only means the screenshot agrees
// with itself, and only a second source (level 2) or signed data (level 3) can add real assurance.
export default function AssurancePanel({ assurance }) {
  if (!assurance) return null;
  const blocked = ["contradiction", "possible_issue", "conflict", "review"].includes(assurance.status);
  return (
    <section className={`card assurance assurance--l${assurance.level}${blocked ? " assurance--blocked" : ""}`} aria-labelledby="assurance-heading" data-testid="assurance-panel">
      <h3 id="assurance-heading" className="card__title">Assurance: level {assurance.level} of 3 - {assurance.label}</h3>
      <ol className="ladder" aria-label="Assurance levels">
        {assurance.ladder.map((step) => (
          <li key={step.level} className={`ladder__step${step.reached ? " is-reached" : ""}${step.level === assurance.level ? " is-current" : ""}`} data-testid="ladder-step">
            <span className="ladder__num">{step.level}</span>
            <span>
              <strong>{step.label}</strong>
              <span className="muted ladder__req"> {step.requirement}</span>
            </span>
          </li>
        ))}
      </ol>
      {assurance.reasons.length > 0 && (
        <ul className="why" data-testid="assurance-reasons">
          {assurance.reasons.map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}
      {assurance.nextStep && <p><strong>Next:</strong> {assurance.nextStep}</p>}
      {assurance.note && <p className="muted">{assurance.note}</p>}
    </section>
  );
}
