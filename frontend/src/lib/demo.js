import evidence from "../fixtures/evidence.json";
import suspicious from "../fixtures/suspicious.json";
import noEvidence from "../fixtures/no_evidence.json";
import inconclusive from "../fixtures/inconclusive.json";

// Demo mode (`?demo=evidence|suspicious|no_evidence|inconclusive`) renders a
// fixture result with a generated placeholder image, without calling the
// backend. Used for the review presentation and for tests.
export const DEMO_FIXTURES = {
  evidence,
  suspicious,
  no_evidence: noEvidence,
  inconclusive,
};

export const DEMO_LABELS = {
  evidence: "Evidence",
  suspicious: "Suspicious",
  no_evidence: "No evidence",
  inconclusive: "Inconclusive",
};

export function getDemoKey(search) {
  const s = search ?? (typeof window !== "undefined" ? window.location.search : "");
  const key = new URLSearchParams(s).get("demo");
  return key && Object.prototype.hasOwnProperty.call(DEMO_FIXTURES, key) ? key : null;
}

// ---------------------------------------------------------------------------
// Placeholder receipt layout. Monospace text with a fixed advance (CHAR_W)
// makes every word's box deterministic, so the fixtures' region coordinates
// line up with the drawn text.
// ---------------------------------------------------------------------------
export const RECEIPT = {
  width: 750,
  height: 1334,
  fontSize: 36,
  charW: 22,
  rightEdge: 690,
  labelX: 60,
  wordH: 44,
  rows: [
    { label: "To", value: "Northwind Coffee", top: 520 },
    { label: "Date", value: "Fri, 14 Mar 2023", top: 610 },
    { label: "Reference", value: "TXN-48213390", top: 700 },
    { label: "Method", value: "Visa ****4417", top: 790 },
    { label: "Subtotal", value: "$349.00", top: 880 },
    { label: "Tax", value: "$50.90", top: 970 },
    { label: "Total", value: "$399.90", top: 1060 },
  ],
};

/** Word boxes (original-image pixels) of the base receipt. */
export function receiptWordBoxes() {
  const { charW, rightEdge, wordH, rows } = RECEIPT;
  const boxes = [];
  for (const row of rows) {
    const startX = rightEdge - row.value.length * charW;
    let cursor = 0;
    for (const word of row.value.split(" ")) {
      boxes.push({
        text: word,
        x: startX + cursor * charW,
        y: row.top + 20,
        w: word.length * charW,
        h: wordH,
      });
      cursor += word.length + 1;
    }
  }
  return boxes;
}

const overlaps = (a, b) =>
  a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

const MONO = 'ui-monospace, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace';

function drawWord(ctx, word) {
  // Fit the word into its box horizontally so it lines up whatever font is used.
  ctx.save();
  ctx.font = `600 ${RECEIPT.fontSize}px ${MONO}`;
  const natural = ctx.measureText(word.text).width || word.w;
  ctx.translate(word.x, word.y + word.h / 2);
  ctx.scale(word.w / natural, 1);
  ctx.fillStyle = "#1c2433";
  ctx.textBaseline = "middle";
  ctx.fillText(word.text, 0, 0);
  ctx.restore();
}

function drawReceipt(ctx, regions) {
  const { width, height, rows, labelX } = RECEIPT;
  ctx.fillStyle = "#eceff5";
  ctx.fillRect(0, 0, width, height);

  // status bar
  ctx.fillStyle = "#1c2433";
  ctx.font = `600 26px ${MONO}`;
  ctx.textBaseline = "middle";
  ctx.fillText("9:41", 36, 44);
  ctx.textAlign = "right";
  ctx.fillText("LTE  87%", width - 36, 44);

  // header
  ctx.textAlign = "center";
  ctx.fillStyle = "#2b6cb0";
  ctx.beginPath();
  ctx.arc(width / 2, 190, 54, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "#fff";
  ctx.lineWidth = 9;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(width / 2 - 24, 192);
  ctx.lineTo(width / 2 - 6, 210);
  ctx.lineTo(width / 2 + 26, 172);
  ctx.stroke();
  ctx.fillStyle = "#1c2433";
  ctx.font = `700 42px ${MONO}`;
  ctx.fillText("Payment sent", width / 2, 300);
  ctx.fillStyle = "#6b7488";
  ctx.font = `500 28px ${MONO}`;
  ctx.fillText("Transaction receipt", width / 2, 350);

  // card
  ctx.fillStyle = "#ffffff";
  ctx.beginPath();
  ctx.roundRect ? ctx.roundRect(30, 470, width - 60, 700, 24) : ctx.rect(30, 470, width - 60, 700);
  ctx.fill();

  ctx.textAlign = "left";
  rows.forEach((row, i) => {
    ctx.fillStyle = "#6b7488";
    ctx.font = `500 30px ${MONO}`;
    ctx.textBaseline = "middle";
    ctx.fillText(row.label, labelX, row.top + 42);
    if (i > 0) {
      ctx.fillStyle = "#e3e7ef";
      ctx.fillRect(labelX, row.top - 4, width - 2 * labelX, 2);
    }
  });

  // Words: base receipt words that no region covers, then the region words
  // themselves (so fixtures can show edited text such as "$399.901").
  const regionBoxes = regions.map((r) => ({ x: r.x, y: r.y, w: r.w, h: r.h, text: r.text }));
  for (const w of receiptWordBoxes()) {
    if (!regionBoxes.some((r) => overlaps(r, w))) drawWord(ctx, w);
  }
  for (const r of regionBoxes) if (r.text) drawWord(ctx, r);

  ctx.fillStyle = "#8a93a6";
  ctx.font = `500 26px ${MONO}`;
  ctx.textAlign = "center";
  ctx.fillText("Questions? Contact support", width / 2, 1250);
}

function drawSparse(ctx, width, height) {
  const g = ctx.createLinearGradient(0, 0, width, height);
  g.addColorStop(0, "#3c4a63");
  g.addColorStop(1, "#8795ad");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, width, height);
  ctx.fillStyle = "rgba(255,255,255,0.18)";
  ctx.beginPath();
  ctx.arc(width * 0.7, height * 0.38, height * 0.22, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "rgba(255,255,255,0.85)";
  ctx.font = `600 34px ${MONO}`;
  ctx.textAlign = "left";
  ctx.fillText("OPEN  9-5", 36, height - 40);
}

/**
 * Draw the placeholder image for a fixture and return a data URL
 * (or null when canvas is unavailable, e.g. in jsdom).
 */
export function renderDemoImage(fixture, doc = typeof document !== "undefined" ? document : null) {
  if (!doc) return null;
  const { width, height } = fixture.image;
  const canvas = doc.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext?.("2d");
  if (!ctx) return null;
  if (fixture.verdict === "inconclusive") drawSparse(ctx, width, height);
  else drawReceipt(ctx, fixture.regions);
  try {
    return canvas.toDataURL("image/png");
  } catch {
    return null;
  }
}
