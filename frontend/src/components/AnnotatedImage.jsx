import { useState } from "react";
import { regionToPercentBox } from "../lib/overlay.js";
import { LEVEL_LABELS, pct } from "../lib/result.js";

export const BOX_PAD_PX = 3; // breathing room around each word, in original pixels

export default function AnnotatedImage({
  imageUrl,
  image,
  regions,
  activeIndex,
  selectedIndex,
  onHover,
  onSelect,
}) {
  const [showMarkers, setShowMarkers] = useState(true);
  const hasSize = image.width > 0 && image.height > 0;
  const ratio = hasSize ? image.width / image.height : 4 / 3;
  const alt = regions.length
    ? `Uploaded screenshot with ${regions.length} marked ${regions.length === 1 ? "region" : "regions"}`
    : "Uploaded screenshot";

  return (
    <figure className="annot">
      <figcaption className="annot__bar">
        <span className="annot__title">Your image</span>
        {regions.length > 0 && (
          <label className="toggle">
            <input
              type="checkbox"
              checked={showMarkers}
              onChange={(e) => setShowMarkers(e.target.checked)}
            />
            <span>Show markers</span>
          </label>
        )}
      </figcaption>

      <div
        className="annot__stage"
        style={{
          aspectRatio: `${ratio}`,
          // keep very tall screenshots inside the viewport
          width: `min(100%, calc(80vh * ${ratio}))`,
        }}
      >
        {imageUrl ? (
          <img className="annot__img" src={imageUrl} alt={alt} />
        ) : (
          <div className="annot__missing">Image preview unavailable</div>
        )}

        {showMarkers && (
          <div className="annot__layer" data-testid="overlay-layer">
            {regions.map((r, i) => {
              const box = regionToPercentBox(r, image, BOX_PAD_PX);
              if (!box) return null;
              const active = activeIndex === i;
              const dim = activeIndex != null && !active;
              return (
                <button
                  key={i}
                  type="button"
                  data-testid="region-box"
                  className={[
                    "rbox",
                    `rbox--${r.level}`,
                    active ? "is-active" : "",
                    selectedIndex === i ? "is-selected" : "",
                    dim ? "is-dim" : "",
                  ].join(" ")}
                  style={box}
                  aria-label={`Region ${i + 1}: "${r.text}", ${LEVEL_LABELS[r.level].toLowerCase()}, ${r.source === "rule" ? "rule check" : `score ${pct(r.score)}`}`}
                  aria-pressed={selectedIndex === i}
                  onMouseEnter={() => onHover(i)}
                  onMouseLeave={() => onHover(null)}
                  onFocus={() => onHover(i)}
                  onBlur={() => onHover(null)}
                  onClick={() => onSelect(i)}
                >
                  <span className="rbox__badge" aria-hidden="true">{i + 1}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {regions.length > 0 && (
        <ul className="legend" aria-label="Marker colours">
          <li><span className="swatch swatch--evidence" />Strong signal</li>
          <li><span className="swatch swatch--suspicious" />Suspicious</li>
          <li><span className="swatch swatch--weak" />Weak signal</li>
        </ul>
      )}
    </figure>
  );
}
