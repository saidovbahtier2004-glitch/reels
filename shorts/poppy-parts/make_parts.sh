#!/bin/bash
# Split a 16:9 video into vertical 9:16 Shorts parts (each < 2 min).
# Usage: ./make_parts.sh input.mp4
set -e
IN="$1"; FONT=/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf
CUTS=(0 89.5 192.0 275.1 384.9 477.3 566.1 620.3)
N=$((${#CUTS[@]}-1))
for i in $(seq 1 $N); do
  S=${CUTS[$((i-1))]}; E=${CUTS[$i]}; D=$(echo "$E-$S" | bc)
  NEXT=""; [ $i -lt $N ] && NEXT=",drawtext=fontfile=$FONT:text='PART $((i+1)) NEXT':fontsize=64:fontcolor=white:borderw=6:bordercolor=black:x=(w-tw)/2:y=1560:enable='gte(t,$D-6)'"
  ffmpeg -loglevel error -y -ss $S -t $D -i "$IN" -filter_complex "\
[0:v]split[a][b];\
[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=24:3,eq=brightness=-0.12:saturation=1.2[bg];\
[b]scale=-2:820:flags=lanczos,crop=1080:820,unsharp=5:5:0.8[fg];\
[bg][fg]overlay=0:550,\
drawtext=fontfile=$FONT:text='PART $i':fontsize=120:fontcolor=0xFFE066:borderw=10:bordercolor=black:x=(w-tw)/2:y=300$NEXT,\
fade=t=in:st=0:d=0.3,fade=t=out:st=$(echo "$D-0.4"|bc):d=0.4[v];\
[0:a]afade=t=in:st=0:d=0.3,afade=t=out:st=$(echo "$D-0.4"|bc):d=0.4,loudnorm=I=-14:TP=-1.5:LRA=11[a]" \
  -map "[v]" -map "[a]" -r 30 -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart "part_$i.mp4"
  echo "part_$i: ${D}s"
done
