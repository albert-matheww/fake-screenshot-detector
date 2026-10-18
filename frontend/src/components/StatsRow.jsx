import { formatDuration, pct } from "../lib/result.js";

export default function StatsRow({ stats, meta, image }) {
  const items = [
    ["Words read", stats.ocr_words],
    ["Words measured", stats.measured_words],
    ["Strongest word signal", stats.top_word_probability != null ? pct(stats.top_word_probability) : null],
    ["Processing time", meta.processing_ms != null ? formatDuration(meta.processing_ms) : null],
    ["Image", image.width ? `${image.width} x ${image.height}${image.format ? ` ${image.format}` : ""}` : null],
    ["Model", meta.model],
  ].filter(([, v]) => v != null && v !== "");
  return (
    <section aria-label="Analysis details">
      <dl className="stats">
        {items.map(([label, value]) => (
          <div className="stat" key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {meta.sha256 && (
        <p className="hash" title={meta.sha256}>
          SHA-256 <code>{meta.sha256.slice(0, 16)}...</code>
        </p>
      )}
    </section>
  );
}
