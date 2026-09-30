#!/usr/bin/env bash
# Requires Kaggle API credentials (~/.kaggle/kaggle.json) and accepting the competition rules.
set -euo pipefail
mkdir -p data/raw
kaggle competitions download -c rossmann-store-sales -p data/raw
unzip -o data/raw/rossmann-store-sales.zip -d data/raw
rm -f data/raw/rossmann-store-sales.zip data/raw/test.csv   # test.csv has no Sales — not used
