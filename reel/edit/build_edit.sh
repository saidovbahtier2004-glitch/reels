#!/usr/bin/env bash
# Talking-head edit pipeline: frames+face (once) -> audio -> 60 fps render (3 workers) -> mux
set -e; cd "$(dirname "$0")"; mkdir -p out
[ -d frames ] && [ "$(ls frames | wc -l)" -gt 100 ] || { mkdir -p frames; ffmpeg -v error -y -i source.mp4 -vf fps=60 -q:v 3 frames/%05d.jpg; }
[ -f face.json ] || python3 face.py
python3 edit_audio.py
rm -rf out/seg; python3 edit_render.py video 3 out/seg
for i in 0 1 2; do echo "file 'seg/seg$i.mp4'"; done > out/list.txt
ffmpeg -v error -y -f concat -i out/list.txt -c copy out/pic.mp4
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 out/pic.mp4)
ffmpeg -y -v error -i out/pic.mp4 -i source.mp4 -i music.wav -i sfx.wav -filter_complex \
"[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0,highpass=f=70,acompressor=threshold=-22dB:ratio=3:attack=5:release=120,loudnorm=I=-16:TP=-2[v0];[v0]asplit=2[v][vsc];\
[2:a]volume=0.5[m];[m][vsc]sidechaincompress=threshold=0.03:ratio=8:attack=10:release=250[md];\
[3:a]volume=0.75[s];[v][md][s]amix=inputs=3:normalize=0:duration=longest,loudnorm=I=-14:TP=-1.5:LRA=9,apad,atrim=0:$D[a]" \
-map 0:v -map "[a]" -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p -profile:v high -level 4.2 -r 60 -c:a aac -b:a 256k -movflags +faststart out/reels_edit_1080p60.mp4
echo done
