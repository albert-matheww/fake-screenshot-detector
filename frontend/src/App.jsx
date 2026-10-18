import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ImageUpload from "./components/ImageUpload.jsx";
import AnalysisResults from "./components/AnalysisResults.jsx";
import LoadingPanel from "./components/LoadingPanel.jsx";
import ErrorPanel from "./components/ErrorPanel.jsx";
import ModelStatus from "./components/ModelStatus.jsx";
import ComparePanel from "./components/ComparePanel.jsx";
import { analyzeImage, getStatus, toApiError } from "./services/api.js";
import { normalizeResult } from "./lib/result.js";
import { DEMO_FIXTURES, DEMO_LABELS, getDemoKey, renderDemoImage } from "./lib/demo.js";
import { SearchMinusIcon, SpinnerIcon, LockIcon } from "./icons.jsx";

export default function App() {
  const [demoKey, setDemoKey] = useState(() => getDemoKey());
  const [mode, setMode] = useState("analyse");
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [apiStatus, setApiStatus] = useState({ state: "checking", info: null });
  const abortRef = useRef(null);

  // Demo mode: fixture result + generated placeholder image, no backend calls.
  const demoImageUrl = useMemo(
    () => (demoKey ? renderDemoImage(DEMO_FIXTURES[demoKey]) : null),
    [demoKey],
  );
  const shownResult = demoKey ? DEMO_FIXTURES[demoKey] : result;
  const shownImageUrl = demoKey ? demoImageUrl : previewUrl;

  useEffect(() => {
    if (demoKey) {
      setApiStatus({ state: "demo", info: null });
      return undefined;
    }
    const controller = new AbortController();
    getStatus({ signal: controller.signal })
      .then((info) => {
        const state = !info?.model ? "online" : info.model.loaded ? "ok" : "not_loaded";
        setApiStatus({ state, info });
      })
      .catch((err) => {
        if (err?.code !== "ERR_CANCELED") setApiStatus({ state: "down", info: null });
      });
    return () => controller.abort();
  }, [demoKey]);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return undefined;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleFileSelected = (selectedFile) => {
    setFile(selectedFile);
    setResult(null);
    setError(null);
  };

  const handleAnalyze = useCallback(async () => {
    if (!file) return;
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await analyzeImage(file, { signal: controller.signal });
      if (!normalizeResult(data)) {
        setError({
          kind: "bad_response",
          message: "The server replied, but not in a format this page understands. The backend and frontend versions may not match.",
          retryable: false,
        });
      } else {
        setResult(data);
      }
    } catch (err) {
      const apiErr = toApiError(err);
      if (apiErr.kind !== "canceled") setError(apiErr);
    } finally {
      abortRef.current = null;
      setLoading(false);
    }
  }, [file]);

  const handleCancel = () => abortRef.current?.abort();

  const reset = () => {
    abortRef.current?.abort();
    if (demoKey) {
      setDemoKey(null);
      window.history.replaceState({}, "", window.location.pathname);
    }
    setFile(null);
    setResult(null);
    setError(null);
  };

  const showPreview = previewUrl && !shownResult && !demoKey;

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand">
          <div className="app__logo" aria-hidden="true">
            <SearchMinusIcon size={24} />
          </div>
          <div>
            <h1>Fake Screenshot Detector</h1>
            <p className="app__tagline">
              Finds signs of editing in screenshots - and tells you what it can&apos;t see.
            </p>
          </div>
        </div>
        <ModelStatus state={apiStatus.state} info={apiStatus.info} />
      </header>

      {demoKey && (
        <nav className="demobar" aria-label="Demo examples">
          <span className="demobar__label">Demo - example results, no server call</span>
          <ul>
            {Object.keys(DEMO_FIXTURES).map((key) => (
              <li key={key}>
                <a href={`?demo=${key}`} aria-current={key === demoKey ? "page" : undefined}>
                  {DEMO_LABELS[key]}
                </a>
              </li>
            ))}
          </ul>
        </nav>
      )}

      {!demoKey && (
        <nav className="modebar" aria-label="Mode">
          <button type="button" className={`modebar__tab${mode === "analyse" ? " is-active" : ""}`} aria-pressed={mode === "analyse"} onClick={() => setMode("analyse")}>
            Check one screenshot
          </button>
          <button type="button" className={`modebar__tab${mode === "compare" ? " is-active" : ""}`} aria-pressed={mode === "compare"} onClick={() => setMode("compare")}>
            Compare with a genuine copy
          </button>
        </nav>
      )}

      <main className="app__main">
        {!demoKey && mode === "compare" && <ComparePanel />}
        {!demoKey && mode === "analyse" && !shownResult && <ImageUpload onFileSelected={handleFileSelected} disabled={loading} />}

        {mode === "analyse" && showPreview && (
          <div className="preview-card">
            <img src={previewUrl} alt="Selected screenshot preview" />
            {loading ? (
              <LoadingPanel onCancel={handleCancel} />
            ) : (
              <div className="preview-card__actions">
                <button type="button" className="button" onClick={handleAnalyze} disabled={!file}>
                  {loading && <SpinnerIcon size={16} />}
                  Analyse
                </button>
                <button type="button" className="button button--ghost" onClick={reset}>
                  Clear
                </button>
              </div>
            )}
          </div>
        )}

        {!loading && <ErrorPanel error={error} onRetry={file ? handleAnalyze : null} onClear={reset} />}

        {(demoKey || mode === "analyse") && shownResult && (
          <AnalysisResults result={shownResult} imageUrl={shownImageUrl} onReset={reset} />
        )}
      </main>

      <footer className="app__footer">
        <p>
          <LockIcon size={16} />
          Images are analyzed in memory and are not stored. Results are an automated
          screening aid, not a certified forensic determination.
        </p>
      </footer>
    </div>
  );
}
