# BeatCut Reels: automatic Reels editor

Upload a raw video, pick a style, press **AUTO EDIT**, preview it with sound, adjust anything, and export a 1080×1920 Reel.
Everything runs in the browser. Your video is never uploaded, unless you choose the OpenAI subtitle option.

## What changed from the previous BeatCut Reels

Everything the old app did still works. The beat-synced montage is now a style, **Beat Montage**, with "cut every N beats" and story/highlights clip selection. The old silence threshold and shortest-pause controls are still there. So are the alternating zoom in/out per clip, the beat pulse, and crossfade, flash, dip, zoom-punch and whip transitions. The seven colour looks, vignette, grain and letterbox bars are kept, as are whoosh and impact sounds, music ducking, 720/1080 and 25/30/60 fps, and saved settings.

Fixed and new:
* **Missing original audio.** The old app needed a music file, read the video's sound only through `decodeAudioData` (which fails on many iPhone `.mov` files), and played the preview through Web Audio, which the iPhone silent switch mutes. Now music is optional, and the video's audio is decoded with a second decoder (WebCodecs) when the first one fails. The preview plays the real mix through an audio element, and the export writes the same mix into the file.
* **Frame-accurate MP4 export** where the browser supports it. Real-time recording remains as the fallback.
* Speech-aware pause and filler removal, subject-aware punch zooms, speed ramps, light leaks, glitch, motion blur, camera shake, risers and bass hits. Also animated subtitles in five styles (via Whisper speech recognition or an `.srt`), a hook title, lower third, CTA, and an editable list for every cut, zoom, transition and sound effect.

## Motion graphics (HyperFrames-style)

Each preset applies its own set of motion-graphics templates on top of **your** footage. They are composited into the exported video, not just the preview:

| Preset | Title card | Other graphics | Transitions |
|---|---|---|---|
| Viral Reels | stacked colour bars, words pop in | kinetic keywords, ring + arrow callout on the subject during punch-ins, progress bar | zoom blast, wipe, flash, whip |
| Cinematic | serif, letter-spacing settles, gold rules | animated cinema bars, light leaks | light leak, soft flash, whip |
| Podcast | clean text with accent underline | lower third, karaoke captions, jump-cut reframing | hard cuts |
| Sports / MMA | slanted stripes, slam-in with shake | tracking reticle on the subject, kinetic keywords, SLOW-MO tag on speed ramps, speed lines | whip, wipe, flash, glitch, zoom blast |
| Product Ad | white card with drawn underline | labelled pointer callouts, light sweeps | soft flash, wipe, zoom blast |
| Tech Promo | full-screen headline: each line fills the frame width, letters rise in one by one with RGB split, white flash, red rule and red light sweep | oversized keywords on a red or white band (cropped while they land, tracking expands), targeting brackets on the subject, scan lines, yellow-green glowing call to action | glitch (with a glitch sound), white or red flash, whip, zoom blast, wipe |
| Clean & Minimal | small fading text | none (on purpose) | hard cuts |
| Beat Montage | stacked (Bebas) | beat-frame pulse on every downbeat | crossfade, wipe, flash, zoom blast, whip, dip, all on the beat |

Rules that keep it from looking random:
* Text is never invented. Titles use your hook text, or the first spoken sentence if subtitles exist. Kinetic keywords use real subtitle words.
* Callouts only appear where a subject was actually detected (skin tone or motion heuristics).
* Titles and keywords move to a different band of the frame when the subject is in the way.
* Captions hide while a title or keyword repeats the same words.
* Tech Promo puts a sound on every graphic: a bass hit on the title card, an impact on each keyword, a riser into the call to action and a glitch sound on glitch cuts.

Every graphic is listed under **Adjust → Effects**, where you can switch each one off and preview it.

### About HyperFrames

[HyperFrames](https://github.com/heygen-com/hyperframes) (HeyGen, Apache-2.0) describes videos as HTML compositions: timed clips (`data-start`, `data-duration`, `data-track-index`) that can be seeked to any frame. Its MP4 renderer, `@hyperframes/engine` and `@hyperframes/producer`, runs the composition in **headless Chrome through Puppeteer and encodes with FFmpeg on Node.js 22+**. GitHub Pages is static hosting, and iPhone Safari can't run Node, Puppeteer or FFmpeg. Its in-browser player only plays compositions and cannot export your clip with graphics burned in.

So this app does **not** run HyperFrames code. It uses the same composition model (timed, seekable clips on tracks), rendered natively into the canvas that the WebCodecs/MediaRecorder exporter already encodes. No server, no paid API.

## Files

| File | Purpose |
|---|---|
| `index.html` | Page layout and styles |
| `app.js` | All editor logic: analysis, auto edit, audio mix, WebGL effects, captions, preview, export |
| `vendor/mediabunny.min.mjs` | MP4/WebM demuxing, decoding, encoding and muxing ([Mediabunny](https://github.com/Vanilagy/mediabunny), MPL-2.0) |
| `vendor/MEDIABUNNY-LICENSE.txt` | Licence for the file above |

Keep the folder structure exactly as it is. `app.js` loads `vendor/mediabunny.min.mjs` by relative path.

## Publish on GitHub Pages

**From a computer**
1. Open your repository on github.com (or create one with **New repository**, set to *Public*).
2. Click **Add file → Upload files**. Drag in `index.html`, `app.js`, `README.md` and the whole `vendor` folder, then click **Commit changes**.
3. Go to **Settings → Pages**. Under *Build and deployment*, set **Source: Deploy from a branch**, **Branch: main**, folder **/ (root)**, then click **Save**.
4. After about a minute your app is live at `https://<your-username>.github.io/<repo-name>/`.

**From an iPhone** (Safari, github.com website)
1. Save the files to the Files app. Then open your repo in Safari, tap **Add file → Upload files**, and choose `index.html`, `app.js` and `README.md`.
2. The `vendor` folder has to exist on GitHub. Tap **Add file → Create new file**, type `vendor/x` as the name (typing `/` creates the folder), and commit. Open the new `vendor` folder, choose **Add file → Upload files**, and upload `mediabunny.min.mjs` and `MEDIABUNNY-LICENSE.txt`. Then delete the placeholder file `x`.
3. Turn Pages on as in step 3 above.

The app must be served over **https** (GitHub Pages does this). Opening `index.html` directly from the Files app won't work, because browsers block JavaScript modules on `file://`.

To test on a computer: `python3 -m http.server` in this folder, then open http://localhost:8000.

## How to use

1. **Upload** a video. On iPhone, tap *Options* in the picker and choose **Most Compatible** if a HEVC video won't load.
2. Choose a **style**: Viral Reels, Cinematic, Podcast, Sports/MMA, Product Ad or Clean & Minimal. Also choose an **intensity** (subtle/balanced/aggressive) and an optional target length.
3. Optionally add **your own music**. The app never adds music by itself.
4. Optionally pick **subtitles**: on-device Whisper (free, downloads a 40–80 MB model once), the OpenAI API (your key), or your own `.srt`.
5. Press **AUTO EDIT** and watch the preview. The sound comes from the real edited mix.
6. Use the **Adjust** tabs to change cuts, zooms, transitions, colour, the volume of each audio layer, subtitles and titles.
7. Press **EXPORT VIDEO**. On iPhone, tap **Save / Share → Save Video** to put it in Photos.

## What is real, what is experimental

The full table is inside the app under “What is real and what is experimental?”. In short:

* **Working:** original audio in the preview and the export. Silence, pause and dead-time removal (loudness analysis with padding so words aren't clipped). Scene and motion analysis. Subject-aware zooms (skin-tone and motion heuristics, not face recognition). Beat detection and beat sync. Music ducking. Synthesized sound effects. WebGL colour grading, glow, light leaks, flashes, whip pans, motion blur, shake, glitch and speed ramps. Five animated subtitle styles. Kinetic hook title, lower third and CTA. Frame-accurate MP4 export, with a real-time recording fallback.
* **Experimental:**
  * On-device speech recognition. It is a real ML model (Whisper), but the first download is large and long videos are slow on phones.
  * Filler-word and restart removal. It depends on the transcript, and Whisper often leaves out "um"/"uh".
  * Target-length trimming.
  * Content-type suggestion. It is rule-based, not AI.
* **External:** the OpenAI Whisper API sends your audio to OpenAI and needs your API key.

No part of the app calls itself "AI" unless a real model is involved. The only real model is the Whisper speech recognition.

## Export notes (iPhone / Safari)

* **Frame-accurate export** uses WebCodecs to encode H.264 + AAC into MP4. It renders every frame exactly, at any speed. It needs both a video and an audio encoder, which Chrome, Edge and Android have. Safari supports it only in versions that include the WebCodecs `AudioEncoder`.
* If that isn't available, the app falls back to **real-time recording** with MediaRecorder: canvas and the mixed audio, saved as MP4 on Safari. This takes as long as the video. Keep Safari in the foreground with the screen on. The app asks the screen to stay awake where it's supported.
* Either way, the exported file includes the full mixed soundtrack: original audio, music and effects.

## Troubleshooting (iPhone)

When you press AUTO EDIT, the log under the progress bar shows:
* your browser and its capabilities (WebCodecs decoders and encoders, WebGL2, MediaRecorder);
* the file's container and codecs, and whether each track can be decoded;
* which method decoded the original audio. The app tries three, in this order: (1) copy the audio track into a small .m4a and decode it with Web Audio, (2) decode with WebCodecs, (3) decode the whole file with Web Audio.

If the original audio can't be decoded, AUTO EDIT **stops** and lists why each method failed, instead of quietly making a silent edit. You can then try again, re-save the clip from Photos as *Most Compatible*, or tap **Continue without original audio**.

If the video won't open, the message includes the browser's own media error code and reason.

