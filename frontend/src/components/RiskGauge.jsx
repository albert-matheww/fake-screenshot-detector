import { TIERS, pct } from "../lib/result.js";

// A zoned track with the two tier boundaries marked. The marker position is
// the risk score; the zones make clear that the number only means something
// relative to 40% / 70%.
export default function RiskGauge({ score }) {
  const s = Math.min(Math.max(Number(score) || 0, 0), 1);
  return (
    <div className="gauge">
      <div className="gauge__head">
        <span className="gauge__title" id="risk-gauge-title">Risk score</span>
        <span className="gauge__value">{pct(s)}</span>
      </div>
      <div
        className="gauge__track"
        role="meter"
        aria-labelledby="risk-gauge-title"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(s * 100)}
        aria-valuetext={`${pct(s)} risk. Review recommended from ${pct(TIERS.suspicious)}; evidence of editing from ${pct(TIERS.evidence)}.`}
      >
        <span className="gauge__zone gauge__zone--low" style={{ width: `${TIERS.suspicious * 100}%` }} />
        <span
          className="gauge__zone gauge__zone--mid"
          style={{ left: `${TIERS.suspicious * 100}%`, width: `${(TIERS.evidence - TIERS.suspicious) * 100}%` }}
        />
        <span
          className="gauge__zone gauge__zone--high"
          style={{ left: `${TIERS.evidence * 100}%`, width: `${(1 - TIERS.evidence) * 100}%` }}
        />
        <span className="gauge__fill" style={{ width: `${s * 100}%` }} />
        <span className="gauge__marker" style={{ left: `${s * 100}%` }} />
      </div>
      <div className="gauge__ticks" aria-hidden="true">
        <span className="gauge__tick" style={{ left: "0%" }}>
          <b>0%</b>
        </span>
        <span className="gauge__tick" style={{ left: `${TIERS.suspicious * 100}%` }}>
          <b>{pct(TIERS.suspicious)}</b>
          <i>suspicious</i>
        </span>
        <span className="gauge__tick" style={{ left: `${TIERS.evidence * 100}%` }}>
          <b>{pct(TIERS.evidence)}</b>
          <i>evidence</i>
        </span>
        <span className="gauge__tick" style={{ left: "100%" }}>
          <b>100%</b>
        </span>
      </div>
    </div>
  );
}
