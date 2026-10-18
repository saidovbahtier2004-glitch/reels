#!/usr/bin/env bash
# Full pipeline: timeline -> audio -> 4K frames (3 parallel Chromium workers) -> encode -> mux -> 1080p
set -e; cd "$(dirname "$0")"; mkdir -p out
python3 timeline.py && python3 audio.py
rm -rf out/seg; python3 render.py video 2 3 out/seg
for i in 0 1 2; do echo "file 'seg/seg$i.mp4'"; done > out/list.txt
ffmpeg -v error -y -f concat -i out/list.txt -c copy out/picture_raw.mp4
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 out/picture_raw.mp4)
ffmpeg -v error -y -i out/picture_raw.mp4 -c:v libx264 -preset medium -crf 20 -maxrate 45M -bufsize 90M -pix_fmt yuv420p -profile:v high -level 5.1 -movflags +faststart -an out/reels_picture_4k.mp4
ffmpeg -v error -y -i out/reels_picture_4k.mp4 -i out/music.wav -i out/sfx.wav -filter_complex "[1:a]volume=0.6[a];[2:a]volume=0.8[b];[a][b]amix=inputs=2:normalize=0,loudnorm=I=-14:TP=-1.5:LRA=9,atrim=0:$D,afade=t=out:st=$(python3 -c "print($D-0.77)"):d=0.77[o]" -map 0:v -map "[o]" -c:v copy -c:a aac -b:a 256k -ar 48000 -movflags +faststart out/reels_final_4k.mp4
ffmpeg -v error -y -i out/reels_final_4k.mp4 -vf "scale=1080:1920:flags=lanczos" -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p -profile:v high -level 4.2 -c:a copy -movflags +faststart out/reels_final_1080p.mp4
echo done
