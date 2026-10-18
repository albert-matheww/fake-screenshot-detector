import { AlertTriangleIcon } from "../icons.jsx";

const TITLES = {
  network: "Can't reach the server",
  timeout: "Analysis timed out",
  too_large: "Image too large",
  invalid_image: "That file can't be analysed",
  rate_limited: "Please slow down",
  server: "The server hit an error",
  bad_response: "Unexpected response",
  unknown: "Something went wrong",
};

export default function ErrorPanel({ error, onRetry, onClear }) {
  if (!error) return null;
  return (
    <div className={`errorpanel errorpanel--${error.kind}`} role="alert" data-testid="error-panel">
      <AlertTriangleIcon size={20} />
      <div className="errorpanel__body">
        <p className="errorpanel__title">{TITLES[error.kind] ?? TITLES.unknown}</p>
        <p className="errorpanel__msg">{error.message}</p>
      </div>
      <div className="errorpanel__actions">
        {onRetry && error.retryable !== false && (
          <button type="button" className="button button--sm" onClick={onRetry}>
            Try again
          </button>
        )}
        {onClear && (
          <button type="button" className="button button--ghost button--sm" onClick={onClear}>
            Choose another image
          </button>
        )}
      </div>
    </div>
  );
}
