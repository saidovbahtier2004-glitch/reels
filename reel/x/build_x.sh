#!/usr/bin/env bash
# "Exclusive" edit pipeline: denoised frames -> word alignment -> audio -> 60 fps render -> mux (H.264 + H.265)
set -e; cd "$(dirname "$0")"; mkdir -p out
[ "$(ls frames 2>/dev/null | wc -l)" -gt 100 ] || { mkdir -p frames; ffmpeg -v error -y -i source.mp4 -vf "fps=60,hqdn3d=1.5:1.5:3:3,unsharp=5:5:0.55:3:3:0" -q:v 2 frames/%05d.jpg; }
python3 align2.py source.mp4 words_prior.json words.json
python3 x_audio.py
rm -rf out/seg; python3 x_render.py video 3 out/seg
for i in 0 1 2; do echo "file 'seg/seg$i.mp4'"; done > out/list.txt
ffmpeg -v error -y -f concat -i out/list.txt -c copy out/pic.mp4
D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 out/pic.mp4)
AF="[1:a]aresample=48000,pan=stereo|c0=c0|c1=c0,highpass=f=70,acompressor=threshold=-22dB:ratio=3:attack=5:release=120,loudnorm=I=-16:TP=-2[v0];[v0]asplit=2[v][vsc];[2:a]volume=0.5[m];[m][vsc]sidechaincompress=threshold=0.03:ratio=8:attack=10:release=250[md];[3:a]volume=0.75[s];[v][md][s]amix=inputs=3:normalize=0:duration=longest,loudnorm=I=-14:TP=-1.5:LRA=9,apad,atrim=0:$D[a]"
VF="unsharp=3:3:0.35:3:3:0"
ffmpeg -y -v error -i out/pic.mp4 -i source.mp4 -i music.wav -i sfx.wav -filter_complex "[0:v]${VF}[vv];$AF" -map "[vv]" -map "[a]" -c:v libx264 -preset slow -crf 16 -pix_fmt yuv420p -profile:v high -level 4.2 -r 60 -c:a aac -b:a 256k -movflags +faststart out/reels_exclusive_1080p60_h264.mp4
ffmpeg -y -v error -i out/reels_exclusive_1080p60_h264.mp4 -c:v libx265 -preset medium -crf 20 -pix_fmt yuv420p -tag:v hvc1 -c:a copy -movflags +faststart out/reels_exclusive_1080p60_h265.mp4
echo done
