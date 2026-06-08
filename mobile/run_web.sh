#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "[web] Building Flutter web app..."
flutter build web

echo "[web] Serving build/web on http://localhost:3000"
python3 -m http.server 3000 --directory build/web
