import { useEffect, useMemo, useState } from "react";
import ImageUpload from "./components/ImageUpload.jsx";
import AnalysisResults from "./components/AnalysisResults.jsx";
import { analyzeImage } from "./services/api.js";
import { ShieldCheckIcon, SpinnerIcon, LockIcon } from "./icons.jsx";

export default function App() {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!file) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setPreviewUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  const handleFileSelected = (selectedFile) => {
    setFile(selectedFile);
    setResult(null);
    setError("");
  };

  const handleAnalyze = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const data = await analyzeImage(file);
      setResult(data);
    } catch (err) {
      const message =
        err?.response?.data?.error || err?.message || "Analysis failed. Please try again.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const reset = () => {
    setFile(null);
    setResult(null);
    setError("");
  };

  const canAnalyze = useMemo(() => Boolean(file) && !loading, [file, loading]);

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__logo">
          <ShieldCheckIcon size={26} />
        </div>
        <div className="app__header-text">
          <p className="app__eyebrow">Forensic analysis</p>
          <h1>Screenshot Forensics</h1>
          <p>Upload a chat or bank statement screenshot to check it for signs of tampering.</p>
        </div>
      </header>

      <main className="app__main">
        <ImageUpload onFileSelected={handleFileSelected} disabled={loading} />

        {previewUrl && !result && (
          <div className="preview-card">
            <img src={previewUrl} alt="Selected screenshot preview" />
            <div className="preview-card__actions">
              <button className="button" onClick={handleAnalyze} disabled={!canAnalyze}>
                {loading && <SpinnerIcon size={16} />}
                {loading ? "Analyzing…" : "Analyze"}
              </button>
              <button className="button button--ghost" onClick={reset} disabled={loading}>
                Clear
              </button>
            </div>
          </div>
        )}

        {error && <p className="error-text error-text--banner">{error}</p>}

        {result && (
          <AnalysisResults result={result} originalPreviewUrl={previewUrl} onReset={reset} />
        )}
      </main>

      <footer className="app__footer">
        <p>
          <LockIcon size={16} />
          Images are analyzed in memory and are not stored. This tool provides an
          automated heuristic signal, not a certified forensic determination.
        </p>
      </footer>
    </div>
  );
}
