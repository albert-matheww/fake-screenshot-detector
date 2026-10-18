import { clamp } from "./overlay.js";

// Tier boundaries of the (monotone) risk score. Mirrors the backend contract.
export const TIERS = { suspicious: 0.4, evidence: 0.7 };

export const VERDICTS = {
  evidence_of_editing: {
    tone: "evidence",
    defaultLabel: "Inconsistency found",
    summary:
      "A calibrated check found a contradiction in this screenshot. Look at the marked areas and confirm with the issuer.",
  },
  suspicious: {
    tone: "suspicious",
    defaultLabel: "Possible inconsistency - review recommended",
    summary:
      "A calibrated check found something unusual but not conclusive. A person should look at it before trusting this image.",
  },
  no_evidence: {
    tone: "no_evidence",
    defaultLabel: "No inconsistency found by the checks that could run",
    summary:
      "The calibrated checks found nothing contradictory. This is not proof that the image is untouched: a careful edit leaves nothing for them to find.",
  },
  inconclusive: {
    tone: "inconclusive",
    defaultLabel: "Inconclusive - verify with the issuer",
    summary:
      "The checks that could examine this screenshot are not enough to say anything either way. Verify the claim with the issuer.",
  },
};

// Used only if a response arrives with an empty `limitations` array, so the
// "cannot tell you" panel is never blank.
export const FALLBACK_LIMITATIONS = [
  "This tool looks for inconsistencies between words inside one image. It cannot show that an image is untouched.",
  "It is an automated screening aid, not a certified forensic opinion.",
];

export const LEVEL_LABELS = {
  evidence: "Strong signal",
  suspicious: "Suspicious",
  weak: "Weak signal",
};

export const SEVERITY_LABELS = { high: "High", medium: "Medium", low: "Low" };

export function pct(value, digits = 0) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  return `${(n * 100).toFixed(digits)}%`;
}

export function formatDuration(ms) {
  const n = Number(ms);
  if (!Number.isFinite(n)) return "-";
  return n >= 1000 ? `${(n / 1000).toFixed(1)} s` : `${Math.round(n)} ms`;
}

const asStringArray = (v) => (Array.isArray(v) ? v.filter((s) => typeof s === "string" && s) : []);

/**
 * Defensive normalisation of the /analyze payload. Returns null when the
 * payload is not a recognisable v2 result (caller shows an error instead of
 * crashing). Legacy alias fields (fake_score, is_fake, verdict_text) are
 * deliberately dropped.
 */
export function normalizeResult(raw) {
  if (!raw || typeof raw !== "object" || !VERDICTS[raw.verdict]) return null;
  const image = {
    width: Number(raw.image?.width) || 0,
    height: Number(raw.image?.height) || 0,
    format: raw.image?.format ?? "",
  };
  const regions = (Array.isArray(raw.regions) ? raw.regions : [])
    .filter((r) => r && [r.x, r.y, r.w, r.h].every(Number.isFinite))
    .map((r) => ({
      x: r.x,
      y: r.y,
      w: r.w,
      h: r.h,
      text: typeof r.text === "string" ? r.text : "",
      score: clamp(Number(r.score) || 0, 0, 1),
      source: r.source === "rule" ? "rule" : "model",
      level: LEVEL_LABELS[r.level] ? r.level : "weak",
      reasons: asStringArray(r.reasons),
    }));
  const findings = (Array.isArray(raw.findings) ? raw.findings : [])
    .filter((f) => f && typeof f.message === "string")
    .map((f) => ({
      id: String(f.id ?? ""),
      severity: SEVERITY_LABELS[f.severity] ? f.severity : "low",
      message: f.message,
      evidence: f.evidence && typeof f.evidence === "object" ? f.evidence : {},
    }));
  const limitations = asStringArray(raw.limitations);
  return {
    verdict: raw.verdict,
    verdict_label: raw.verdict_label || VERDICTS[raw.verdict].defaultLabel,
    risk_score: clamp(Number(raw.risk_score) || 0, 0, 1),
    reasons: asStringArray(raw.reasons),
    regions,
    findings,
    limitations: limitations.length ? limitations : FALLBACK_LIMITATIONS,
    routing: raw.routing && typeof raw.routing === "object" ? raw.routing : null,
    capture: raw.capture && typeof raw.capture === "object" ? raw.capture : null,
    checks: (Array.isArray(raw.checks) ? raw.checks : []).filter((c) => c && typeof c.id === "string"),
    coverage: raw.coverage && typeof raw.coverage === "object" ? raw.coverage : null,
    verifySteps: asStringArray(raw.verify_steps),
    image,
    stats: raw.stats ?? {},
    meta: raw.meta ?? {},
  };
}
