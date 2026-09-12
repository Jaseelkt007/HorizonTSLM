#!/bin/bash
# Download Kelmarsh (Zenodo 5841834) and Penmanshiel (5946808) SCADA + status zips, 2017-2021, CC-BY-4.0 (Cubico).
# Usage: DATA_DIR=~/data scripts/download_data.sh      (default DATA_DIR=./data)
set -u
DATA_DIR="${DATA_DIR:-./data}"
mkdir -p "$DATA_DIR/raw/kelmarsh" "$DATA_DIR/raw/penmanshiel"
cd "$DATA_DIR/raw"
for rec in 5946808:penmanshiel 5841834:kelmarsh; do
  id=${rec%%:*}; name=${rec##*:}
  curl -s "https://zenodo.org/api/records/$id" | python3 -c "
import sys, json
for f in json.load(sys.stdin)['files']:
    k = f['key']
    if 'SCADA' in k and any(y in k for y in ('2017','2018','2019','2020','2021')):
        print(k, f['links']['self'])" | while read -r key url; do
    [ -s "$name/$key" ] && continue
    echo "$(date +%T) $name/$key"; curl -sL -o "$name/$key.part" "$url" && mv "$name/$key.part" "$name/$key"
  done
done
echo "$(date +%T) DONE"; du -sh kelmarsh penmanshiel
