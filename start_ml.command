#!/bin/zsh
# Start the existing Sprint app using the optional ML environment.
cd "$(dirname "$0")" || exit 1
if [[ ! -x .venv/bin/python ]]; then
  print "First follow the four setup steps in README.md."
  exit 1
fi
print "Property ML Lab: http://127.0.0.1:5001/ml-lab"
exec .venv/bin/python app.py
