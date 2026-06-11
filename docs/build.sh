#!/usr/bin/env bash
# Render docs/0*.md into a single PDF using pandoc + xelatex.
# Requires: pandoc and a LaTeX engine (texlive-xetex on Debian/Ubuntu).
set -euo pipefail

cd "$(dirname "$0")"

OUTPUT="esp32-link.pdf"
INPUTS=(
    01-requirements.md
    02-architecture.md
    03-design.md
    04-protocol.md
    05-state-machine.md
    06-testing.md
    07-build-and-run.md
)

pandoc "${INPUTS[@]}" \
    --output "${OUTPUT}" \
    --pdf-engine=xelatex \
    --toc \
    --toc-depth=2 \
    --number-sections \
    --metadata title="esp32-link" \
    --metadata subtitle="Aplikacja okienkowa do komunikacji z płytką ESP32" \
    --metadata author="Paweł Michalcewicz" \
    -V geometry:margin=2.5cm \
    -V mainfont="DejaVu Serif" \
    -V monofont="DejaVu Sans Mono"

echo "Wrote ${OUTPUT}"
