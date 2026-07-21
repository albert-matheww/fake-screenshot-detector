# early experiments

## ela threshold
- 3x3 grid, quality 90 re-encode
- diff threshold 18 catches most copy-paste tampering, but generates
  false hits on anti-aliased text edges
- 24 feels safer for real screenshots

## copy-move window
- 8x8 window, voting with min 6 offsets -> too noisy on chat bubbles
- 16x16 with min 10 offsets is a good middle ground
- anything above 32x32 misses small logos

next: run the same checks on compressed whatsapp exports (they re-encode
everything, ELA basically turns into noise there)
