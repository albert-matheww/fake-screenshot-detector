# api reference

## GET /status
healthcheck, returns {"status": "ok", "model": "rf_v1"}

## POST /analyze
multipart form upload, field name "image".

response:
  {"tamper_score": 0.87,
   "cues": {
     "ela": {"score": 0.9, "detail": "large re-encode regions near text"},
     "exif": {"score": 0.2, "detail": "no metadata found"},
     "ocr": {"score": 0.5, "detail": "font metrics consistent"}
   }}

scores are 0..1, tamper_score is the classifier output on the cue vector.
