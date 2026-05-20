#!/usr/bin/env bash
# exit on error
set -o errexit

# 1. Install regular Python package requirements
pip install -r requirements.txt

# 2. Define path for binary caching
STORAGE_DIR=/opt/render/project/.render

if [ ! -d "$STORAGE_DIR/chrome" ]; then
  echo "--- Downloading and Unpacking Stable Google Chrome ---"
  mkdir -p $STORAGE_DIR/chrome
  cd $STORAGE_DIR/chrome
  
  # Download official stable Google Chrome build for Debian/Ubuntu environments
  wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
  dpkg -x google-chrome-stable_current_amd64.deb .
  rm google-chrome-stable_current_amd64.deb
  
  cd -
  echo "--- Chrome Installation Completed Successfully ---"
else
  echo "--- Chrome instance pulled instantly from application build cache ---"
fi
