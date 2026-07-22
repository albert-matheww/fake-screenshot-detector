# example outputs

## tampered chat screenshot (score 0.87)
- ela flagged the pasted message row
- copy-move found a duplicated avatar region
- exif empty (expected for most chat exports)

## bank statement pdf export (score 0.11)
- only mild jpeg artifacts, consistent with a screenshot of a pdf
- ocr font metrics consistent

## edited amount on a receipt (score 0.63)
- ela lit up around the amount area
- ocr caught mixed font weights in the same line

takeaway: single cues are noisy, the classifier combining them is what
carries the detection
