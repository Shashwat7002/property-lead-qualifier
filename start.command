#!/bin/bash
# Sprint Lead Generation — Mac Launcher
# Double-click this file to start the app.

cd "$(dirname "$0")"

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║      Sprint Lead Generation v1.0         ║"
echo "║   Forsyth & North Fulton · FMLS Powered  ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "ERROR: Python 3 is not installed."
  echo "Download it free from: https://www.python.org/downloads/"
  echo ""
  read -p "Press Enter to exit..."
  exit 1
fi

echo "Installing required packages (first run takes ~30 seconds)..."
pip3 install -r requirements.txt --quiet 2>&1 | tail -1
echo ""
echo "Starting Sprint Lead Generation..."
echo "Your browser will open automatically."
echo ""
echo "Keep this window open while using the app."
echo "Press Ctrl+C here to stop the app."
echo ""

python3 app.py
