import { useEffect, useState } from "react";
import { SpinnerIcon } from "../icons.jsx";

export default function LoadingPanel({ onCancel }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const id = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 250);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="loading" role="status" data-testid="loading">
      <SpinnerIcon size={22} />
      <div className="loading__text">
        <p className="loading__title">Analysing screenshot</p>
        <p className="loading__sub">
          Reading the text, then comparing each word with its neighbours.
          {elapsed >= 8 && " Large images can take up to 15 seconds."}
        </p>
      </div>
      <span className="loading__time" aria-label={`${elapsed} seconds elapsed`}>{elapsed}s</span>
      {onCancel && (
        <button type="button" className="button button--ghost button--sm" onClick={onCancel}>
          Cancel
        </button>
      )}
    </div>
  );
}
