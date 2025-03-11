#!/bin/sh

APP_DIR=$(dirname "$0")
# PYTHONPATH=$APP_DIR uvicorn --app-dir $APP_DIR/src main:app --host 127.0.0.1 --port 8080 $@

# accepts exactly the same args as 'python -m uvicorn' does (in exactly the same format),
# EXCEPT the positional arg for 'app' - it's hardcoded to always be 'main:app':
PYTHONPATH=$APP_DIR python $APP_DIR/src/main.py $@
