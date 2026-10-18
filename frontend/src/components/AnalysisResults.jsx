import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import VerdictBanner from "./VerdictBanner.jsx";
import AnnotatedImage from "./AnnotatedImage.jsx";
import RegionList from "./RegionList.jsx";
import FindingsList from "./FindingsList.jsx";
import LimitationsPanel from "./LimitationsPanel.jsx";
import StatsRow from "./StatsRow.jsx";
import ChecksPanel from "./ChecksPanel.jsx";
import { normalizeResult } from "../lib/result.js";

export function downloadJson(data, filename) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export default function AnalysisResults({ result, imageUrl, onReset }) {
  const view = useMemo(() => normalizeResult(result), [result]);
  const [hovered, setHovered] = useState(null);
  const [selected, setSelected] = useState(null);
  const headingRef = useRef(null);

  // Move focus to the verdict so keyboard / screen-reader users land on it.
  useEffect(() => {
    headingRef.current?.focus?.({ preventScroll: false });
  }, [result]);

  const handleSelect = useCallback((i) => {
    setSelected((cur) => (cur === i ? null : i));
    const el = document.getElementById(`region-card-${i}`);
    if (el?.scrollIntoView) {
      const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
      el.scrollIntoView({ block: "nearest", behavior: reduce ? "auto" : "smooth" });
    }
  }, []);

  const handleKeyDown = (e) => {
    if (e.key === "Escape") {
      setSelected(null);
      setHovered(null);
    }
  };

  if (!view) return null;
  const active = hovered ?? selected;

  const handleDownload = () => {
    const tag = result?.meta?.sha256 ? `-${result.meta.sha256.slice(0, 8)}` : "";
    downloadJson(result, `forensic-report${tag}.json`);
  };

  return (
    <div className="results" onKeyDown={handleKeyDown}>
      <VerdictBanner view={view} onDownload={handleDownload} onReset={onReset} ref={headingRef} />

      <div className="results__grid">
        <div className="results__media">
          <AnnotatedImage
            imageUrl={imageUrl}
            image={view.image}
            regions={view.regions}
            activeIndex={active}
            selectedIndex={selected}
            onHover={setHovered}
            onSelect={handleSelect}
          />
        </div>

        <div className="results__details">
          <section className="card" aria-labelledby="why-heading">
            <h3 id="why-heading" className="card__title">Why</h3>
            {view.reasons.length ? (
              <ul className="why">
                {view.reasons.map((reason, i) => (
                  <li key={i}>{reason}</li>
                ))}
              </ul>
            ) : (
              <p className="muted">No specific reasons were reported.</p>
            )}
          </section>

          <RegionList
            regions={view.regions}
            activeIndex={active}
            selectedIndex={selected}
            onHover={setHovered}
            onSelect={handleSelect}
          />

          <ChecksPanel routing={view.routing} checks={view.checks} coverage={view.coverage} verifySteps={view.verifySteps} />

          <FindingsList findings={view.findings} />
        </div>
      </div>

      <LimitationsPanel limitations={view.limitations} />
      <StatsRow stats={view.stats} meta={view.meta} image={view.image} />
    </div>
  );
}
