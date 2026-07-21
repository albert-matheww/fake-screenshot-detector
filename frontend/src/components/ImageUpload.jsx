import { useCallback, useRef, useState } from "react";
import { UploadCloudIcon } from "../icons.jsx";

const ACCEPTED_TYPES = ["image/png", "image/jpeg", "image/jpg", "image/webp"];
const MAX_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB, matches backend MAX_CONTENT_LENGTH

export default function ImageUpload({ onFileSelected, disabled }) {
  const [dragActive, setDragActive] = useState(false);
  const [localError, setLocalError] = useState("");
  const inputRef = useRef(null);

  const validateAndEmit = useCallback(
    (file) => {
      if (!file) return;
      if (!ACCEPTED_TYPES.includes(file.type)) {
        setLocalError("Unsupported file type. Please upload a PNG, JPEG, or WebP image.");
        return;
      }
      if (file.size > MAX_SIZE_BYTES) {
        setLocalError("File is too large (max 10 MB).");
        return;
      }
      setLocalError("");
      onFileSelected(file);
    },
    [onFileSelected]
  );

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    if (disabled) return;
    const file = e.dataTransfer.files?.[0];
    validateAndEmit(file);
  };

  const handleChange = (e) => {
    const file = e.target.files?.[0];
    validateAndEmit(file);
    // allow re-selecting the same file
    e.target.value = "";
  };

  return (
    <div className="upload-wrapper">
      <div
        className={`dropzone ${dragActive ? "dropzone--active" : ""} ${disabled ? "dropzone--disabled" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragActive(true);
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Upload a screenshot to analyze"
      >
        <div className="dropzone__icon">
          <UploadCloudIcon size={22} />
        </div>
        <p className="dropzone__title">Drag & drop a screenshot here</p>
        <p className="dropzone__subtitle">or click to browse (PNG, JPEG, WebP — max 10 MB)</p>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_TYPES.join(",")}
          onChange={handleChange}
          disabled={disabled}
          hidden
        />
      </div>
      {localError && <p className="error-text">{localError}</p>}
    </div>
  );
}
