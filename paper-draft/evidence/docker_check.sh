#!/bin/zsh
# Builds the backend image from the current tree, starts it, queries /status and /analyze with a generated sample, reports size.
cd /Users/albertmathew/Desktop/projects/fake-screenshot-detector
docker build -q -t fsd-backend-final ./backend 2>&1 | tail -1
docker run -d --rm --name fsd-final-check -p 5098:5000 fsd-backend-final >/dev/null
sleep 10
echo "STATUS: $(curl -s localhost:5098/status)"
curl -s -F image=@docs/samples/statement_edited_detected.png localhost:5098/analyze | python3 -c "import sys,json; r=json.load(sys.stdin); print('ANALYZE statement_edited_detected:', r['verdict'], r['risk_score'], [(g['text'],g['score'],g['level']) for g in r['regions'][:2]], 'ms', r['meta']['processing_ms'])"
curl -s -F image=@docs/samples/statement_original.png localhost:5098/analyze | python3 -c "import sys,json; r=json.load(sys.stdin); print('ANALYZE statement_original:', r['verdict'], r['risk_score'], 'ms', r['meta']['processing_ms'])"
docker stop fsd-final-check >/dev/null
echo "IMAGE SIZE: $(docker image ls fsd-backend-final --format '{{.Size}}')"
docker image inspect fsd-backend-final --format 'BASE/CMD: {{.Config.Cmd}}'
