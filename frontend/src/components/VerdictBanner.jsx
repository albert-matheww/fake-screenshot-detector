import { forwardRef } from "react";
import RiskGauge from "./RiskGauge.jsx";
import { VERDICTS } from "../lib/result.js";
import {
  AlertOctagonIcon,
  EyeIcon,
  SearchMinusIcon,
  HelpCircleIcon,
  DownloadIcon,
  RefreshIcon,
} from "../icons.jsx";

// Icon + colour + text all differ per state so the verdict never relies on
// colour alone. Note: no tick / shield anywhere - "no evidence" is not "genuine".
const TONE_ICON = {
  evidence: AlertOctagonIcon,
  suspicious: EyeIcon,
  no_evidence: SearchMinusIcon,
  inconclusive: HelpCircleIcon,
};

const VerdictBanner = forwardRef(function VerdictBanner({ view, onDownload, onReset }, ref) {
  const meta = VERDICTS[view.verdict];
  const Icon = TONE_ICON[meta.tone];
  const showGauge = view.verdict !== "inconclusive";
  return (
    <section className={`verdict verdict--${meta.tone}`} aria-labelledby="verdict-heading">
      <div className="verdict__top">
        <div className="verdict__icon">
          <Icon size={28} />
        </div>
        <div className="verdict__text">
          <p className="verdict__kicker">Result</p>
          <h2 id="verdict-heading" className="verdict__label" tabIndex={-1} ref={ref}>
            {view.verdict_label}
          </h2>
          <p className="verdict__summary">{meta.summary}</p>
        </div>
        <div className="verdict__actions">
          <button type="button" className="button button--ghost" onClick={onDownload}>
            <DownloadIcon size={16} />
            JSON report
          </button>
          {onReset && (
            <button type="button" className="button button--ghost" onClick={onReset}>
              <RefreshIcon size={16} />
              New scan
            </button>
          )}
        </div>
      </div>
      {showGauge && <RiskGauge score={view.risk_score} />}
    </section>
  );
});

export default VerdictBanner;
