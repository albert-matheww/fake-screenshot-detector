#!/bin/zsh
# Re-runs the evaluations whose numbers appear in the report and stores their output next to this script.
cd /Users/albertmathew/Desktop/projects/fake-screenshot-detector
E=paper-draft/evidence
PY=/Users/albertmathew/Desktop/projects/fake-screenshot-detector/backend/venv/bin/python
export OMP_THREAD_LIMIT=1
( cd backend && $PY -W ignore tools/forge/compare_legacy.py --data ../data/forge_v6 --n 500 ) 2>&1 | grep -v OMP > $E/compare_legacy.txt
( cd backend && $PY -W ignore tools/forge/eval_layout_rule.py --data ../data/forge_v6 ) 2>&1 | grep -v OMP > $E/layout_rule_eval.txt
( cd backend && $PY -W ignore /Users/albertmathew/Desktop/projects/fake-screenshot-detector/paper-draft/evidence/cross.py ) 2>&1 | grep -v OMP > $E/cross_engine.txt
OMP_THREAD_LIMIT=2 $PY -W ignore $E/real8_eval.py 2>&1 | grep -v OMP > $E/real8_results.txt
( cd backend && OMP_THREAD_LIMIT=2 $PY -W ignore -m pytest tests -q ) 2>&1 | tail -5 > $E/pytest.txt
( cd frontend && npx --no-install vitest run ) 2>&1 | tail -14 > $E/vitest.txt
echo finished > $E/_done
