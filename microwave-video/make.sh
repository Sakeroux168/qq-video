#!/bin/bash
# 用法: ./make.sh 02 → out/镜头02.mp4 + 成片抽帧检查图 frames/s02/video_sheet.png
cd "$(dirname "$0")"
N=$1
node lib/render.js shots/s$N.js out/镜头$N.mp4 >/dev/null || { echo FAIL $N; exit 1; }
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 out/镜头$N.mp4)
mkdir -p frames/s$N
python3 - "$N" "$D" <<'PY'
import sys, subprocess
from PIL import Image
n, d = sys.argv[1], float(sys.argv[2])
ts=[d*0.15, d*0.45, d*0.75, d-0.1]
ims=[]
for i,t in enumerate(ts):
    f=f'frames/s{n}/v{i}.png'
    subprocess.run(['ffmpeg','-v','error','-y','-ss',f'{t:.2f}','-i',f'out/镜头{n}.mp4','-frames:v','1',f],check=True)
    ims.append(Image.open(f))
c=Image.new('RGB',(1120*4-40,1920),'white');x=0
for i in ims: c.paste(i,(x,0)); x+=1120
c.resize((c.width*640//1920,640)).save(f'frames/s{n}/video_sheet.png')
PY
echo "DONE $N $D"
