#!/usr/bin/env bash
# Usage: ./add_voice.sh voice.(m4a|wav|mp3) [out.mp4]
# Mixes YOUR recorded voice-over over the finished picture. Music is ducked under the voice (sidechain),
# SFX stay as designed, final loudness -14 LUFS / -1.5 dBTP. Video stream is copied (no re-encode).
set -e; cd "$(dirname "$0")"; V="$1"; O="${2:-out/reels_with_voice.mp4}"
ffmpeg -y -v error -i out/reels_picture_4k.mp4 -i out/music.wav -i out/sfx.wav -i "$V" -filter_complex \
"[3:a]aresample=48000,pan=stereo|c0=c0|c1=c0,highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=5:release=120,loudnorm=I=-16:TP=-2[v0];[v0]asplit=2[v][vsc];\
[1:a]volume=0.55[m];[m][vsc]sidechaincompress=threshold=0.03:ratio=8:attack=10:release=250[md];\
[2:a]volume=0.75[s];[v][md][s]amix=inputs=3:normalize=0:duration=longest,loudnorm=I=-14:TP=-1.5:LRA=9[a]" \
-map 0:v -map "[a]" -c:v copy -c:a aac -b:a 256k -shortest -movflags +faststart "$O"
echo "wrote $O"
