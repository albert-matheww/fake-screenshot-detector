import { SCREENSHOT_TYPES } from "../lib/checks.js";

export default function TypePicker({ id = "shot-type", value, onChange, disabled }) {
  return (
    <div className="typepicker">
      <label htmlFor={id}>What kind of screenshot is this?</label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} disabled={disabled}>
        {SCREENSHOT_TYPES.map((t) => (
          <option key={t.value} value={t.value}>{t.label}</option>
        ))}
      </select>
      <span className="muted">Choosing the type switches on the checks written for it.</span>
    </div>
  );
}
