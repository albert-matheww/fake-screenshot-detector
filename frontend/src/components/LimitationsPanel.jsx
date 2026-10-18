import { InfoIcon } from "../icons.jsx";

// Always rendered with every result, whatever the verdict. Strings are
// shown verbatim as supplied by the backend.
export default function LimitationsPanel({ limitations }) {
  return (
    <section className="limits" aria-labelledby="limits-heading" data-testid="limitations">
      <h3 id="limits-heading" className="limits__title">
        <InfoIcon size={18} />
        What this cannot tell you
      </h3>
      <ul className="limits__list">
        {limitations.map((text, i) => (
          <li key={i}>{text}</li>
        ))}
      </ul>
    </section>
  );
}
