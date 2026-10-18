#!/bin/bash
# two-pass build: render, read page numbers, rebuild with them
set -e
cd "$(dirname "$0")"
ND=/private/tmp/claude-501/-Users-albertmathew-Desktop-projects-fake-screenshot-detector/dd5abb74-8524-43e1-980c-664131e23a6d/scratchpad/deck_node/node_modules
SOF="/Users/albertmathew/Library/Application Support/Claude/local-agent-mode-sessions/skills-plugin/56ea86e1-2863-4265-82dc-6cb350417686/6f813d3f-d851-459c-a87a-4e5012dc7aaf/skills/docx/scripts/office/soffice.py"
W=/private/tmp/claude-501/-Users-albertmathew-Desktop-projects-fake-screenshot-detector/dd5abb74-8524-43e1-980c-664131e23a6d/scratchpad/render2
cp paper_final.md paper.md
rm -f toc_pages.json
for pass in 1 2 3; do
  NODE_PATH=$ND node build_report.js $( [ -f toc_pages.json ] && echo toc_pages.json ) 2>&1 | grep -v -i warning | grep -v trace-warn
  rm -rf $W; mkdir -p $W
  cp reports/Albert_Mathew_Sunil_23BCE1765_Project_Report.docx $W/r.docx
  (cd $W && python3 "$SOF" --headless --convert-to pdf r.docx >/dev/null 2>&1)
  /Users/albertmathew/Desktop/projects/fake-screenshot-detector/backend/venv/bin/python toc_pass.py $W/r.pdf reports/_outline.json toc_pages_new.json
  if [ -f toc_pages.json ] && cmp -s toc_pages.json toc_pages_new.json; then echo "stable after pass $pass"; break; fi
  mv toc_pages_new.json toc_pages.json
done
