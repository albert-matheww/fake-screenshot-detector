import { LEVEL_LABELS, pct } from "../lib/result.js";

export default function RegionList({ regions, activeIndex, selectedIndex, onHover, onSelect }) {
  if (!regions.length) {
    return (
      <section className="card" aria-labelledby="regions-heading">
        <h3 id="regions-heading" className="card__title">Marked words</h3>
        <p className="muted">No individual words were flagged.</p>
      </section>
    );
  }
  return (
    <section className="card" aria-labelledby="regions-heading">
      <h3 id="regions-heading" className="card__title">
        Marked words <span className="count">{regions.length}</span>
      </h3>
      <ol className="regions">
        {regions.map((r, i) => (
          <li
            key={i}
            id={`region-card-${i}`}
            data-testid="region-card"
            className={[
              "rcard",
              `rcard--${r.level}`,
              activeIndex === i ? "is-active" : "",
              selectedIndex === i ? "is-selected" : "",
            ].join(" ")}
            onMouseEnter={() => onHover(i)}
            onMouseLeave={() => onHover(null)}
          >
            <button
              type="button"
              className="rcard__head"
              aria-pressed={selectedIndex === i}
              onClick={() => onSelect(i)}
              onFocus={() => onHover(i)}
              onBlur={() => onHover(null)}
            >
              <span className="rcard__num" aria-hidden="true">{i + 1}</span>
              <span className="rcard__word">{r.text ? `"${r.text}"` : "(unreadable)"}</span>
              <span className={`chip chip--${r.level}`}>{LEVEL_LABELS[r.level]}</span>
              <span className="rcard__score" title={r.source === "rule" ? "Found by a rule check, not by the model" : "Model score for this word"}>
                {r.source === "rule" ? "rule check" : pct(r.score)}
              </span>
            </button>
            {r.source !== "rule" && (
              <div className="rcard__bar" aria-hidden="true">
                <span style={{ width: pct(r.score) }} />
              </div>
            )}
            {r.reasons.length > 0 && (
              <ul className="rcard__reasons">
                {r.reasons.map((reason, j) => (
                  <li key={j}>{reason}</li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ol>
    </section>
  );
}
