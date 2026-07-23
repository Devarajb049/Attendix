#!/usr/bin/env bash
# exit on error
set -o errexit

# Set Playwright path
export PLAYWRIGHT_BROWSERS_PATH=$HOME/.cache/ms-playwright

pip install -r requirements.txt
playwright install chromium
