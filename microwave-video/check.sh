#!/bin/bash
# 用法: ./check.sh 02 0.5,3,5.5  → frames/s02/sheet.png
cd "$(dirname "$0")"
N=$1; TS=$2
rm -rf frames/s$N; node lib/render.js shots/s$N.js frames/s$N --at $TS >/dev/null || exit 1
python3 - "$N" "$TS" <<'PY'
import sys
from PIL import Image
n, ts = sys.argv[1], sys.argv[2].split(',')
ims=[Image.open(f'frames/s{n}/t{float(t):.2f}.png') for t in ts]
c=Image.new('RGB',(1120*len(ims)-40,1920),'white');x=0
for i in ims: c.paste(i,(x,0)); x+=1120
c.resize((c.width*640//1920,640)).save(f'frames/s{n}/sheet.png')
PY
echo frames/s$N/sheet.png
