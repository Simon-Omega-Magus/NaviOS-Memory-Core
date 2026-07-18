#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
OUTPUT=${1:-/tmp/navios-memory-reflex-demo-draft.mp4}
BUILD=$(mktemp -d)
trap 'rm -rf "$BUILD"' EXIT

for command in ffmpeg ffprobe espeak-ng; do
  if ! command -v "$command" >/dev/null 2>&1; then
    printf 'missing required command: %s\n' "$command" >&2
    exit 2
  fi
done

ffmpeg -y -loglevel error \
  -i "$ROOT/media/navios-memory-reflex-closing.svg" -frames:v 1 \
  "$BUILD/closing.png"

images=(
  "$ROOT/media/navios-memory-reflex-thumbnail.png"
  "$ROOT/media/navios-memory-reflex-architecture.png"
  "$ROOT/media/navios-memory-reflex-proof.png"
  "$ROOT/media/navios-memory-reflex-architecture.png"
  "$ROOT/media/navios-memory-reflex-proof.png"
  "$ROOT/media/navios-memory-reflex-thumbnail.png"
  "$BUILD/closing.png"
)

for number in 01 02 03 04 05 06 07; do
  narration=$(find "$ROOT/media/video-narration" -name "${number}-*.txt" -print -quit)
  espeak-ng -v en-us -s 150 -p 48 -a 140 -f "$narration" \
    -w "$BUILD/${number}.wav"
  ffmpeg -y -loglevel error -loop 1 -framerate 30 \
    -i "${images[$((10#$number - 1))]}" -i "$BUILD/${number}.wav" \
    -vf "scale=1600:900:force_original_aspect_ratio=decrease,pad=1600:900:(ow-iw)/2:(oh-ih)/2:#07111f,format=yuv420p" \
    -c:v libx264 -preset medium -tune stillimage -crf 20 \
    -af "volume=-3dB" -c:a aac -b:a 160k -shortest "$BUILD/${number}.mp4"
done

for number in 01 02 03 04 05 06 07; do
  printf "file '%s/%s.mp4'\n" "$BUILD" "$number"
done > "$BUILD/segments.txt"

ffmpeg -y -loglevel error -f concat -safe 0 -i "$BUILD/segments.txt" \
  -c copy -movflags +faststart "$OUTPUT"

duration=$(ffprobe -v error -show_entries format=duration \
  -of default=noprint_wrappers=1:nokey=1 "$OUTPUT")
printf 'rendered %s (%0.1f seconds)\n' "$OUTPUT" "$duration"
