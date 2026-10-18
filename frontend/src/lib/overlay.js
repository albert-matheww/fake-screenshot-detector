// Pure geometry helpers for the region overlay. Regions arrive in pixel
// coordinates of the ORIGINAL uploaded image; the image is shown at an
// arbitrary size, so boxes have to be scaled.

export function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

/**
 * Scale a region from original-image pixels to a displayed size.
 *
 * @param {{x:number,y:number,w:number,h:number}} region  original-image pixels
 * @param {{width:number,height:number}} image            original image size
 * @param {{width:number,height:number}} displayed        displayed size (any unit)
 * @param {number} pad  optional padding in ORIGINAL pixels, applied before scaling
 * @returns {{left:number,top:number,width:number,height:number}|null}
 *   null when the inputs are unusable or the clamped box is empty.
 */
export function scaleRegion(region, image, displayed, pad = 0) {
  const iw = Number(image?.width);
  const ih = Number(image?.height);
  const dw = Number(displayed?.width);
  const dh = Number(displayed?.height);
  if (!region || !(iw > 0) || !(ih > 0) || !(dw > 0) || !(dh > 0)) return null;
  const { x, y, w, h } = region;
  if (![x, y, w, h].every(Number.isFinite)) return null;

  const x0 = clamp(x - pad, 0, iw);
  const y0 = clamp(y - pad, 0, ih);
  const x1 = clamp(x + w + pad, 0, iw);
  const y1 = clamp(y + h + pad, 0, ih);
  if (x1 <= x0 || y1 <= y0) return null;

  const sx = dw / iw;
  const sy = dh / ih;
  return {
    left: x0 * sx,
    top: y0 * sy,
    width: (x1 - x0) * sx,
    height: (y1 - y0) * sy,
  };
}

/**
 * Percent-based box (relative to the image). Percentages follow the image as
 * it resizes, so the overlay stays aligned without any resize handling.
 */
export function regionToPercentBox(region, image, pad = 0) {
  const box = scaleRegion(region, image, { width: 100, height: 100 }, pad);
  if (!box) return null;
  return {
    left: `${box.left}%`,
    top: `${box.top}%`,
    width: `${box.width}%`,
    height: `${box.height}%`,
  };
}
