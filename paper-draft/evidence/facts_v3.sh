#!/bin/bash
# Facts about the version-3 code base (run from the repository root).
cd "$(dirname "$0")/../.."
echo "== lines of code"
wc -l backend/app.py backend/screencheck/*.py backend/textforensics.py backend/semantic.py | sed 's#^ *##'
echo "== frontend components"; ls frontend/src/components/*.jsx | grep -v test | wc -l
echo "== versions"; backend/venv/bin/python --version; tesseract --version 2>&1 | head -1
grep -E "^(Flask|Pillow|numpy|scikit-learn|scipy|pytesseract|gunicorn|joblib|flask-cors)" backend/requirements.txt
echo "== checks"; grep -n "^ALL_IDS" backend/screencheck/checks.py
echo "== data"; ls data/stfd/extracted/STFD_ICASSP2023/*/tamper 2>/dev/null | grep -c png
echo "== git"; git log --oneline | wc -l
