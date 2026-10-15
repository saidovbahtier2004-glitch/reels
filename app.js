// BeatCut Reels — automatic Reels editor (app.js)
// All processing happens locally in the browser. Nothing is uploaded unless the user picks the OpenAI option.

/* ============================== 1. UTILITIES ============================== */
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, t) => a + (b - a) * t;
const smoothstep = (t) => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };
const easeOutCubic = (t) => 1 - Math.pow(1 - clamp(t, 0, 1), 3);
const easeInCubic = (t) => Math.pow(clamp(t, 0, 1), 3);
const easeInOutCubic = (t) => { t = clamp(t, 0, 1); return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; };
const easeOutBack = (t, s = 1.70158) => { t = clamp(t, 0, 1) - 1; return t * t * ((s + 1) * t + s) + 1; };
const fmtTime = (s) => { s = Math.max(0, s || 0); const m = Math.floor(s / 60); const r = Math.floor(s % 60); return `${m}:${String(r).padStart(2, '0')}`; };
const fmtTimeMs = (s) => { s = Math.max(0, s || 0); const m = Math.floor(s / 60); return `${m}:${(s % 60).toFixed(2).padStart(5, '0')}`; };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const nextFrame = () => new Promise((r) => requestAnimationFrame(() => r()));
function percentile(arr, p) {
  if (!arr.length) return 0;
  const a = Float32Array.from(arr).sort();
  return a[clamp(Math.floor((a.length - 1) * p), 0, a.length - 1)];
}
function hash1(n) { const x = Math.sin(n * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); }
// smooth 1D value noise in [-1,1]
function noise1(x) { const i = Math.floor(x); const f = x - i; const u = f * f * (3 - 2 * f); return lerp(hash1(i), hash1(i + 1), u) * 2 - 1; }
// Null-safe error text. Safari rejects some media APIs with `null` or bare Events instead of Error objects.
function errText(e) {
  if (e == null) return 'unknown error (the browser reported no details)';
  if (typeof e === 'string') return e;
  if (typeof Event !== 'undefined' && e instanceof Event) {
    const t = e.target; const me = t && t.error;
    if (me) return `${e.type} event — MediaError code ${me.code}${me.message ? ': ' + me.message : ''}`;
    return `${e.type} event`;
  }
  const name = e.name && e.name !== 'Error' ? e.name + ': ' : '';
  if (e.message) return name + e.message;
  try { return name + String(e); } catch (x) { return 'unprintable error'; }
}
function toError(e, context) {
  if (e instanceof Error && !context) return e;
  const err = new Error((context ? context + ': ' : '') + errText(e));
  if (e && e.name) err.name = e.name;
  err.cause = e;
  return err;
}
const MEDIA_ERR = { 1: 'loading was aborted', 2: 'network error while reading the file', 3: 'the browser could not decode the video', 4: 'this video format/codec is not supported by this browser' };
function debounce(fn, ms) { let id; return (...a) => { clearTimeout(id); id = setTimeout(() => fn(...a), ms); }; }
const isIOS = /iP(hone|ad|od)/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);

let MB = null; // Mediabunny (MPL-2.0) — demux/decode/encode/mux MP4 in the browser
async function loadMediabunny() {
  if (MB) return MB;
  try { MB = await import('./vendor/mediabunny.min.mjs'); }
  catch (e) {
    console.warn('local mediabunny failed, trying CDN', e);
    try { MB = await import('https://cdn.jsdelivr.net/npm/mediabunny@1.61.4/dist/bundles/mediabunny.min.mjs'); }
    catch (e2) { console.warn('mediabunny unavailable', e2); MB = null; }
  }
  return MB;
}

let _actx = null;
function getAudioCtx() {
  if (!_actx) {
    const AC = window.AudioContext || window.webkitAudioContext;
    _actx = new AC({ latencyHint: 'playback' });
  }
  return _actx;
}
// iOS: make Web Audio ignore the silent switch (Safari 16.4+)
try { if (navigator.audioSession) navigator.audioSession.type = 'playback'; } catch (e) { /* ignore */ }

/* ============================== 2. PRESETS ============================== */
const STYLES = {
  viral: {
    name: 'Viral Reels', desc: 'Fast cuts, punch zooms, bold word captions',
    keepPause: 0.16, zoomGap: 2.4, zoomAmt: 1.22, zoomType: 'punch', jumpZoom: 1.12, kenBurns: 0,
    transitions: ['zoomblast', 'wipe', 'flash', 'whip'], transRate: 0.75, jumpTransRate: 0.18,
    sfx: { whoosh: 1, impact: 0.45, riser: 1, bass: 0.35 },
    shake: 0.5, ramps: 0.35, beatPulse: 0.6, grade: 'punchy', captions: 'viral', capWords: 3,
    progress: true, graphics: [], highlight: false, motionBlur: true,
  },
  cinematic: {
    name: 'Cinematic', desc: 'Slow push-ins, light leaks, film look, speed ramps',
    keepPause: 0.45, zoomGap: 4.5, zoomAmt: 1.1, zoomType: 'smooth', jumpZoom: 1.06, kenBurns: 0.07,
    transitions: ['leak', 'flashsoft', 'whip'], transRate: 0.85, jumpTransRate: 0,
    sfx: { whoosh: 0.6, impact: 0, riser: 1, bass: 0.7 },
    shake: 0.15, ramps: 1, beatPulse: 0.4, grade: 'teal', captions: 'cinematic', capWords: 5,
    progress: false, graphics: [], highlight: false, motionBlur: true,
  },
  podcast: {
    name: 'Podcast', desc: 'Tight pauses, framing switches, karaoke subtitles',
    keepPause: 0.28, zoomGap: 3.2, zoomAmt: 1.14, zoomType: 'punch', jumpZoom: 1.15, kenBurns: 0.03,
    transitions: [], transRate: 0, jumpTransRate: 0,
    sfx: { whoosh: 0, impact: 0, riser: 0, bass: 0 },
    shake: 0, ramps: 0, beatPulse: 0, grade: 'warm', captions: 'podcast', capWords: 6,
    progress: true, graphics: ['lowerthird'], highlight: false, motionBlur: false,
  },
  sports: {
    name: 'Sports / MMA', desc: 'Highlights, slow-mo, impacts, shake, whips',
    keepPause: 0.1, zoomGap: 1.6, zoomAmt: 1.3, zoomType: 'punch', jumpZoom: 1.1, kenBurns: 0,
    transitions: ['whip', 'wipe', 'flash', 'glitch', 'zoomblast'], transRate: 1, jumpTransRate: 0.6,
    sfx: { whoosh: 1, impact: 1, riser: 1, bass: 1 },
    shake: 1, ramps: 1, beatPulse: 1, grade: 'contrast', captions: 'sports', capWords: 2,
    progress: false, graphics: ['speedlines'], highlight: true, motionBlur: true,
  },
  product: {
    name: 'Product Ad', desc: 'Clean push-ins, light sweeps, bright look',
    keepPause: 0.25, zoomGap: 3, zoomAmt: 1.15, zoomType: 'smooth', jumpZoom: 1.08, kenBurns: 0.05,
    transitions: ['flashsoft', 'wipe', 'zoomblast'], transRate: 0.8, jumpTransRate: 0,
    sfx: { whoosh: 0.8, impact: 0.3, riser: 0.6, bass: 0.3 },
    shake: 0.1, ramps: 0.5, beatPulse: 0.5, grade: 'bright', captions: 'minimal', capWords: 5,
    progress: false, graphics: ['sweep'], highlight: false, motionBlur: true,
  },
  minimal: {
    name: 'Clean & Minimal', desc: 'Gentle cuts, subtle zooms, simple captions',
    keepPause: 0.35, zoomGap: 6, zoomAmt: 1.07, zoomType: 'smooth', jumpZoom: 1.06, kenBurns: 0.02,
    transitions: [], transRate: 0, jumpTransRate: 0,
    sfx: { whoosh: 0, impact: 0, riser: 0, bass: 0 },
    shake: 0, ramps: 0, beatPulse: 0, grade: 'neutral', captions: 'minimal', capWords: 6,
    progress: false, graphics: [], highlight: false, motionBlur: false,
  },
};
STYLES.montage = {
  name: 'Beat Montage', desc: 'Music-video cuts on the beat (needs music)',
  keepPause: 0.2, zoomGap: 2.2, zoomAmt: 1.14, zoomType: 'punch', jumpZoom: 1.12, kenBurns: 0.12,
  transitions: ['crossfade', 'wipe', 'flash', 'zoomblast', 'whip', 'dip'], transRate: 0.5, jumpTransRate: 0.5,
  sfx: { whoosh: 1, impact: 0.6, riser: 0.6, bass: 0.4 },
  shake: 0.3, ramps: 0, beatPulse: 0.6, pulseZoom: 0.03, grade: 'teal', captions: 'viral', capWords: 3,
  progress: false, graphics: [], highlight: true, motionBlur: true, montage: true,
};
for (const k of Object.keys(STYLES)) if (STYLES[k].pulseZoom == null) STYLES[k].pulseZoom = { viral: 0.025, sports: 0.045 }[k] || 0;
const INTENSITY = {
  subtle: { dens: 0.55, pauseMul: 1.9, pad: 1.35, keepFrac: 0.75 },
  balanced: { dens: 1, pauseMul: 1, pad: 1, keepFrac: 0.55 },
  aggressive: { dens: 1.6, pauseMul: 0.5, pad: 0.75, keepFrac: 0.38 },
};
const CAPTION_DEFAULTS = {
  viral: { font: 'Montserrat', upper: true, size: 100, pos: 68, color: '#ffffff', hl: '#ffe14d', stroke: '#000000', words: 3 },
  cinematic: { font: 'Playfair Display', upper: false, size: 80, pos: 78, color: '#ffffff', hl: '#ffcf8a', stroke: '#000000', words: 5 },
  podcast: { font: 'Poppins', upper: false, size: 85, pos: 72, color: '#ffffff', hl: '#22d3ee', stroke: '#000000', words: 6 },
  sports: { font: 'Anton', upper: true, size: 115, pos: 66, color: '#ffffff', hl: '#ffd400', stroke: '#000000', words: 2 },
  minimal: { font: 'Inter', upper: false, size: 72, pos: 80, color: '#ffffff', hl: '#a5f3fc', stroke: '#000000', words: 6 },
};
const GRADES = {
  neutral: { label: 'Natural', exposure: 0, contrast: 1.05, saturation: 1.05, warmth: 0, tint: 0, shadows: 0, highlights: -0.03, split: 0, glow: 0.08, vignette: 0.15, grain: 0, sharpen: 0.15 },
  punchy: { label: 'Punchy social', exposure: 0.03, contrast: 1.16, saturation: 1.22, warmth: 0.04, tint: 0, shadows: 0.02, highlights: -0.06, split: 0.15, glow: 0.22, vignette: 0.25, grain: 0.02, sharpen: 0.3 },
  teal: { label: 'Cinematic teal & orange', exposure: -0.02, contrast: 1.14, saturation: 0.95, warmth: 0.05, tint: 0, shadows: 0.03, highlights: -0.1, split: 0.65, glow: 0.35, vignette: 0.42, grain: 0.07, sharpen: 0.1 },
  warm: { label: 'Warm podcast', exposure: 0.02, contrast: 1.08, saturation: 1.08, warmth: 0.1, tint: 0.01, shadows: 0.03, highlights: -0.05, split: 0.1, glow: 0.14, vignette: 0.22, grain: 0.015, sharpen: 0.2 },
  contrast: { label: 'High-contrast sports', exposure: 0, contrast: 1.3, saturation: 1.15, warmth: -0.05, tint: 0, shadows: -0.02, highlights: -0.08, split: 0.3, glow: 0.2, vignette: 0.35, grain: 0.04, sharpen: 0.45 },
  bright: { label: 'Bright commercial', exposure: 0.06, contrast: 1.06, saturation: 1.1, warmth: 0.02, tint: 0, shadows: 0.05, highlights: -0.08, split: 0, glow: 0.3, vignette: 0.08, grain: 0, sharpen: 0.3 },
  warmFilm: { label: 'Warm film', exposure: 0.02, contrast: 1.06, saturation: 0.9, warmth: 0.14, tint: 0.01, shadows: 0.06, highlights: -0.06, split: 0.1, glow: 0.2, vignette: 0.3, grain: 0.05, sharpen: 0.1 },
  moody: { label: 'Moody', exposure: -0.06, contrast: 1.22, saturation: 0.72, warmth: -0.06, tint: 0, shadows: -0.04, highlights: -0.12, split: 0.35, glow: 0.15, vignette: 0.5, grain: 0.04, sharpen: 0.15 },
  vivid: { label: 'Vivid pop', exposure: 0.03, contrast: 1.12, saturation: 1.38, warmth: 0.02, tint: 0, shadows: 0.02, highlights: -0.04, split: 0.05, glow: 0.2, vignette: 0.15, grain: 0, sharpen: 0.35 },
  vintage: { label: 'Vintage fade', exposure: 0.02, contrast: 0.9, saturation: 0.74, warmth: 0.1, tint: 0.03, shadows: 0.12, highlights: -0.08, split: 0.2, glow: 0.15, vignette: 0.35, grain: 0.09, sharpen: 0 },
  bw: { label: 'Black & white film', exposure: 0, contrast: 1.25, saturation: 0, warmth: 0, tint: 0, shadows: 0, highlights: -0.05, split: 0, glow: 0.2, vignette: 0.4, grain: 0.09, sharpen: 0.2 },
};
const LOOK_SLIDERS = [
  ['exposure', 'Exposure', -0.5, 0.5, 0.01], ['contrast', 'Contrast', 0.5, 1.6, 0.01], ['saturation', 'Saturation', 0, 2, 0.01],
  ['warmth', 'Warmth', -0.4, 0.4, 0.01], ['tint', 'Tint', -0.3, 0.3, 0.01], ['shadows', 'Shadows', -0.3, 0.3, 0.01],
  ['highlights', 'Highlights', -0.3, 0.3, 0.01], ['split', 'Teal & orange', 0, 1, 0.01], ['glow', 'Glow / bloom', 0, 1, 0.01],
  ['vignette', 'Vignette', 0, 1, 0.01], ['grain', 'Film grain', 0, 0.3, 0.005], ['sharpen', 'Sharpen', 0, 1, 0.01],
];

/* ============================== 3. STATE ============================== */
const PERSIST_KEYS = ['style', 'intensity', 'targetLen', 'framing', 'removeFillers', 'volOrig', 'volMusic', 'volSfx', 'duck', 'duckAmt', 'normalize',
  'beatsPerCut', 'contentMode', 'silAuto', 'silDb', 'minPause', 'letterbox', 'transType', 'transFreq', 'autoTitle'];
function saveSettings() { try { const o = {}; for (const k of PERSIST_KEYS) o[k] = state.settings[k]; localStorage.setItem('beatcut-v2-settings', JSON.stringify(o)); } catch (e) { } }
function loadSavedSettings() { try { return JSON.parse(localStorage.getItem('beatcut-v2-settings') || '{}'); } catch (e) { return {}; } }
const state = {
  file: null, url: null,
  meta: null,              // {duration, width, height}
  origAudio: null,         // AudioBuffer of original soundtrack (null if none)
  analysis: null,          // see analyzeAll()
  music: null,             // {file, buffer, beats, ...}
  transcript: null,        // {words:[{w,s,e}], source, estimated}
  edit: null,              // built edit decision list
  mix: null,               // rendered AudioBuffer of final mix
  settings: {
    style: 'viral', intensity: 'balanced', targetLen: 0, framing: 'smart', removeFillers: true,
    zoomGlobal: 1, jumpZoom: true,
    fx: { transitions: true, shake: true, motionBlur: true, ramps: true, beatPulse: true, graphics: true, progress: true },
    look: { ...GRADES.punchy }, grade: 'punchy',
    volOrig: 1, volMusic: 0.7, volSfx: 0.8, duck: true, duckAmt: 0.75, normalize: true, musicOffset: 0,
    subsOn: true, cap: { style: 'viral', ...CAPTION_DEFAULTS.viral, keywords: true },
    hookText: '', lowerThird: '', ctaText: '', autoTitle: true,
    // carried over from BeatCut Reels
    beatsPerCut: 'auto', contentMode: 'sequential', silAuto: true, silDb: -40, minPause: 0, letterbox: false,
    pulseZoom: 0.025, drift: 'style', driftAmt: 0.12, transType: 'auto', transFreq: 1,
  },
};

/* ============================== 4. ANALYSIS ============================== */
// Decode an audio track from a media File into an AudioBuffer. Returns null if the file has no audio.
// Probe the container with Mediabunny: container, tracks, codecs, and whether this browser can decode each.
async function probeMedia(file) {
  await loadMediabunny();
  if (!MB) return { error: 'media library unavailable' };
  try {
    const input = new MB.Input({ source: new MB.BlobSource(file), formats: MB.ALL_FORMATS });
    const fmt = await input.getFormat();
    const out = { container: fmt && fmt.name, video: [], audio: [] };
    for (const t of await input.getVideoTracks()) out.video.push({ codec: t.codec, coded: `${t.codedWidth}×${t.codedHeight}`, rotation: t.rotation, canDecode: await t.canDecode().catch(() => false) });
    for (const t of await input.getAudioTracks()) out.audio.push({ codec: t.codec, channels: t.numberOfChannels, rate: t.sampleRate, canDecode: await t.canDecode().catch(() => false) });
    out.input = input;
    return out;
  } catch (e) { return { error: errText(e) }; }
}
function decodeWithWebAudio(ac, ab) {
  return new Promise((res, rej) => {
    let done = false;
    const ok = (b) => { if (!done) { done = true; res(b); } };
    const fail = (e) => { if (!done) { done = true; rej(toError(e, 'decodeAudioData failed')); } };
    try { const p = ac.decodeAudioData(ab, ok, fail); if (p && p.then) p.then(ok, fail); }
    catch (e) { fail(e); }
  });
}
// Decode an audio track from a media File into an AudioBuffer. Returns null if the file has no audio track.
// Routes, in order:
//  A) copy the audio track (no re-encode) into a small .m4a and decode that with Web Audio — works on iOS Safari
//     even without WebCodecs audio, and avoids loading a huge .mov into memory;
//  B) decode the track with WebCodecs (Mediabunny AudioBufferSink);
//  C) decodeAudioData on the whole file (classic path; fails on many iPhone .mov files in Safari).
async function decodeAudioFromFile(file, log, probe) {
  const ac = getAudioCtx();
  const say = (m, c) => log && log(m, c);
  await loadMediabunny();
  if (!probe) probe = await probeMedia(file);
  const tracks = probe && probe.input ? await probe.input.getAudioTracks().catch(() => []) : null;
  if (tracks && tracks.length === 0) { say('The file contains no audio track.', 'warn'); return null; }
  const errors = [];
  const viaRemux = async () => {
    if (!MB || !probe.input) throw new Error('container could not be parsed');
    const inp = new MB.Input({ source: new MB.BlobSource(file), formats: MB.ALL_FORMATS });
    const output = new MB.Output({ format: new MB.Mp4OutputFormat({ fastStart: 'in-memory' }), target: new MB.BufferTarget() });
    const conv = await MB.Conversion.init({ input: inp, output, video: { discard: true }, audio: { forceTranscode: false } });
    if (!conv.isValid) throw new Error('audio track cannot be copied: ' + (conv.discardedTracks || []).map((d) => `${d.track.type}/${d.track.codec || '?'} (${d.reason})`).join(', '));
    await conv.execute();
    const ab = output.target.buffer;
    say(`Audio track copied to a ${(ab.byteLength / 1e6).toFixed(1)} MB .m4a for decoding.`);
    return await decodeWithWebAudio(ac, ab);
  };
  const viaWebCodecs = async () => {
    if (!MB || !probe.input) throw new Error('container could not be parsed');
    if (!('AudioDecoder' in window)) throw new Error('WebCodecs AudioDecoder not available in this browser');
    const inp = new MB.Input({ source: new MB.BlobSource(file), formats: MB.ALL_FORMATS });
    let track = null;
    for (const t of await inp.getAudioTracks()) if (await t.canDecode().catch(() => false)) { track = t; break; }
    if (!track) throw new Error('no audio track this browser can decode');
    const sink = new MB.AudioBufferSink(track);
    const parts = []; let end = 0, sr = 0, ch = 1;
    for await (const w of sink.buffers()) { parts.push(w); sr = w.buffer.sampleRate; ch = Math.max(ch, w.buffer.numberOfChannels); end = Math.max(end, w.timestamp + w.buffer.duration); }
    if (!parts.length) throw new Error('decoder produced no audio');
    const t0 = Math.min(0, parts[0].timestamp);
    const out = new AudioBuffer({ length: Math.ceil((end - t0) * sr), numberOfChannels: Math.min(ch, 2), sampleRate: sr });
    for (const w of parts) {
      const off = Math.round((w.timestamp - t0) * sr);
      for (let c = 0; c < out.numberOfChannels; c++) {
        const src = w.buffer.getChannelData(Math.min(c, w.buffer.numberOfChannels - 1));
        const n = Math.min(src.length, out.length - off);
        if (n > 0 && off >= 0) out.getChannelData(c).set(src.subarray(0, n), off);
      }
    }
    return out;
  };
  const viaWholeFile = async () => {
    if (file.size > 700e6) throw new Error(`file too large (${(file.size / 1e6).toFixed(0)} MB) to load whole into memory`);
    return await decodeWithWebAudio(ac, await file.arrayBuffer());
  };
  for (const [name, fn] of [['copy audio track → Web Audio', viaRemux], ['WebCodecs decoder', viaWebCodecs], ['Web Audio on whole file', viaWholeFile]]) {
    try {
      const b = await fn();
      if (b && b.length) { say(`Original audio decoded via ${name}.`, 'ok'); return b; }
      errors.push(`${name}: empty result`);
    } catch (e) {
      errors.push(`${name}: ${errText(e)}`); console.warn('audio route failed', name, e);
      say(`Audio route “${name}” failed: ${errText(e)}`, 'warn');
    }
  }
  const err = new Error('Could not decode the original audio of this video. ' + errors.join(' | '));
  err.audioDecode = true; throw err;
}

// Render a buffer to mono at a given rate, optionally band-limited (used for voice detection and Whisper input)
async function renderMono(buf, rate, band) {
  const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  let oc, actual = rate;
  try { oc = new OAC(1, Math.max(1, Math.ceil(buf.duration * rate)), rate); }
  catch (e) {
    // Older Safari only accepts 22.05–96 kHz offline contexts: render at the buffer's rate and resample in JS.
    actual = buf.sampleRate; oc = new OAC(1, Math.max(1, Math.ceil(buf.duration * actual)), actual);
    if (band) band = [band[0], Math.min(band[1], rate * 0.45)]; else band = [10, rate * 0.45];
  }
  const out = await renderMonoWith(oc, buf, band);
  return actual === rate ? out : resampleLinear(out, actual, rate);
}
function resampleLinear(x, from, to) {
  const n = Math.floor(x.length * to / from), y = new Float32Array(n), k = from / to;
  for (let i = 0; i < n; i++) { const p = i * k, j = Math.floor(p), f = p - j; y[i] = (x[j] || 0) * (1 - f) + (x[j + 1] || 0) * f; }
  return y;
}
async function renderMonoWith(oc, buf, band) {
  const src = oc.createBufferSource(); src.buffer = buf;
  let node = src;
  if (band) {
    const hp = oc.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = band[0];
    const lp = oc.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = band[1];
    node.connect(hp); hp.connect(lp); node = lp;
  }
  node.connect(oc.destination); src.start(0);
  const r = await oc.startRendering();
  return r.getChannelData(0);
}

function envelopeDb(samples, rate, hop) {
  const n = Math.floor(samples.length / (rate * hop));
  const out = new Float32Array(n); const step = Math.floor(rate * hop);
  for (let i = 0; i < n; i++) {
    let s = 0; const o = i * step;
    for (let j = 0; j < step; j++) { const v = samples[o + j]; s += v * v; }
    out[i] = 10 * Math.log10(s / step + 1e-12);
  }
  return out;
}

// Voice/sound activity detection with adaptive threshold + hysteresis + padding so words are never clipped.
// 150 ms moving maximum: bridges the tiny gaps between syllables so the noise floor reflects real pauses.
function bridgeEnvelope(env, hop) {
  const r = Math.max(1, Math.round(0.075 / hop)), n = env.length, out = new Float32Array(n);
  for (let i = 0; i < n; i++) { let m = -200; for (let j = Math.max(0, i - r); j <= Math.min(n - 1, i + r); j++) if (env[j] > m) m = env[j]; out[i] = m; }
  return out;
}
function detectSoundRegions(rawEnv, hop, dur, o) {
  const env = bridgeEnvelope(rawEnv, hop);
  const valid = Array.from(env).filter((v) => v > -95);
  const noise = valid.length ? percentile(valid, 0.1) : -100, loud = percentile(env, 0.95);
  const range = loud - noise;
  if (loud < -60) return { regions: [], noise, loud, thr: loud };
  if (range < 7) return { regions: [{ s: 0, e: dur }], noise, loud, thr: noise };
  const thrOpen = o.thr != null ? o.thr : Math.max(noise + 6, noise + range * 0.3);
  const thrClose = thrOpen - 4;
  const raw = []; let on = false, st = 0;
  for (let i = 0; i < env.length; i++) {
    if (!on && env[i] > thrOpen) { on = true; st = i; }
    else if (on && env[i] < thrClose) { on = false; raw.push([st, i]); }
  }
  if (on) raw.push([st, env.length]);
  let regs = raw.filter(([a, b]) => {
    const len = (b - a) * hop; if (len >= 0.07) return true;
    let mx = -200; for (let i = a; i < b; i++) mx = Math.max(mx, env[i]); return mx > thrOpen + 10;
  }).map(([a, b]) => {
    // extend tail while still above (thrClose-6) to keep soft word endings, max +0.2s
    let e = b; while (e < env.length && e - b < 0.1 / hop && rawEnv[e] > thrClose - 6) e++;
    let s = a; while (s > 0 && a - s < 0.05 / hop && rawEnv[s - 1] > thrClose - 6) s--;
    return { s: Math.max(0, s * hop - o.padPre), e: Math.min(dur, e * hop + o.padPost) };
  });
  const merged = [];
  for (const r of regs) {
    const last = merged[merged.length - 1];
    if (last && r.s - last.e < o.minGap) last.e = Math.max(last.e, r.e); else merged.push({ ...r });
  }
  return { regions: merged, noise, loud, thr: thrOpen };
}

// Emphasis peaks: syllables noticeably louder than their local context (stressed words, shouts, impacts)
function detectEmphasis(env, hop) {
  const n = env.length, out = [];
  const win = Math.round(1.5 / hop);
  const pre = new Float64Array(n + 1);
  for (let i = 0; i < n; i++) pre[i + 1] = pre[i] + env[i];
  const sm = new Float32Array(n);
  for (let i = 0; i < n; i++) { let s = 0; const a = Math.max(0, i - 2), b = Math.min(n - 1, i + 2); for (let j = a; j <= b; j++) s += env[j]; sm[i] = s / (b - a + 1); }
  const score = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const a = Math.max(0, i - win), b = Math.min(n, i + win);
    const local = (pre[b] - pre[a]) / (b - a);
    const onset = i > 3 ? Math.max(0, sm[i] - sm[i - 4]) : 0;
    score[i] = Math.max(0, sm[i] - local) * 0.6 + onset * 0.4;
  }
  const thr = percentile(score, 0.93);
  const minDist = Math.round(0.3 / hop);
  for (let i = 1; i < n - 1; i++) {
    if (score[i] > thr && score[i] >= score[i - 1] && score[i] >= score[i + 1]) {
      const last = out[out.length - 1];
      if (last && i - last.i < minDist) { if (score[i] > last.v) { last.i = i; last.v = score[i]; } }
      else out.push({ i, v: score[i] });
    }
  }
  const mx = out.reduce((m, p) => Math.max(m, p.v), 1e-6);
  return out.map((p) => ({ t: p.i * hop, v: p.v / mx }));
}

// Speech-likeness: speech has strong 3–8 Hz syllabic loudness modulation inside active regions.
function speechLikeness(env, hop, regions) {
  let diffs = 0, cnt = 0;
  for (const r of regions) {
    const a = Math.floor(r.s / hop), b = Math.floor(r.e / hop);
    for (let i = a + 5; i < b; i += 1) { diffs += Math.abs(env[i] - env[i - 5]); cnt++; }
  }
  return cnt ? diffs / cnt : 0; // dB change per 50 ms; speech typically > 4.5
}

// Sample small frames (via WebCodecs decode when available, else seeking a <video>) to measure motion/scenes/subject position.
async function analyzeFrames(file, url, dur, aspect, onProgress) {
  const N = clamp(Math.round(dur * 4), 16, 480);
  const times = Array.from({ length: N }, (_, i) => (i + 0.5) * dur / N);
  const W = 48, H = Math.max(16, Math.round(48 / aspect));
  const cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const cx = cv.getContext('2d', { willReadFrequently: true });
  const samples = []; let prevL = null, prevH = null;
  const process = (src, t) => {
    cx.drawImage(src, 0, 0, W, H);
    const d = cx.getImageData(0, 0, W, H).data;
    const L = new Float32Array(W * H); const hist = new Float32Array(64);
    let skin = 0, sx = 0, sy = 0, bright = 0;
    for (let p = 0, k = 0; p < d.length; p += 4, k++) {
      const r = d[p], g = d[p + 1], b = d[p + 2];
      const y = 0.299 * r + 0.587 * g + 0.114 * b; L[k] = y; bright += y;
      hist[((r >> 6) << 4) | ((g >> 6) << 2) | (b >> 6)]++;
      const cb = 128 - 0.168736 * r - 0.331264 * g + 0.5 * b, cr = 128 + 0.5 * r - 0.418688 * g - 0.081312 * b;
      if (cb > 77 && cb < 127 && cr > 135 && cr < 173 && y > 50) { skin++; sx += k % W; sy += Math.floor(k / W); }
    }
    let motion = 0, mx = 0, my = 0, mw = 0, scene = 0;
    if (prevL) {
      for (let k = 0; k < L.length; k++) { const df = Math.abs(L[k] - prevL[k]); motion += df; if (df > 18) { mx += (k % W) * df; my += Math.floor(k / W) * df; mw += df; } }
      motion /= L.length * 255;
      for (let i = 0; i < 64; i++) scene += Math.abs(hist[i] - prevH[i]);
      scene /= 2 * L.length;
    }
    samples.push({
      t, motion, scene, bright: bright / L.length / 255,
      skin: skin / L.length, sx: skin ? sx / skin / W : 0.5, sy: skin ? sy / skin / H : 0.4,
      mx: mw ? mx / mw / W : 0.5, my: mw ? my / mw / H : 0.5,
    });
    prevL = L; prevH = hist;
  };
  let usedDecoder = false;
  await loadMediabunny();
  if (MB) {
    try {
      const input = new MB.Input({ source: new MB.BlobSource(file), formats: MB.ALL_FORMATS });
      const vt = await input.getPrimaryVideoTrack();
      if (vt && (await vt.canDecode())) {
        const sink = new MB.CanvasSink(vt, { width: W, height: H, fit: 'fill', poolSize: 2 });
        let i = 0, last = null;
        for await (const wc of sink.canvasesAtTimestamps(times)) {
          const c = wc ? wc.canvas : last; if (c) process(c, times[i]); last = c; i++;
          if (i % 8 === 0) { onProgress(i / N); await sleep(0); }
        }
        usedDecoder = samples.length > N * 0.8;
        if (!usedDecoder) samples.length = 0, prevL = null;
      }
    } catch (e) { console.warn('decoder frame analysis failed, falling back to seeking', errText(e)); samples.length = 0; prevL = null; }
  }
  if (!usedDecoder) {
    // iOS only decodes frames for video elements that are in the page and were started by a tap, so reuse the pool element.
    const v = $('#vidA'); const sub = times.filter((_, i) => i % Math.max(1, Math.ceil(N / 100)) === 0);
    const t0 = performance.now(); let timeouts = 0;
    for (let i = 0; i < sub.length; i++) {
      const ok = await new Promise((r) => { const to = setTimeout(() => r(false), 1500); v.onseeked = () => { clearTimeout(to); r(true); }; v.currentTime = sub[i]; });
      if (!ok) timeouts++;
      if (v.readyState >= 2) process(v, sub[i]);
      onProgress(i / sub.length);
      if (timeouts > 8 || performance.now() - t0 > 90000) { console.warn('frame sampling stopped early', { timeouts }); break; }
    }
    v.onseeked = null;
    if (!samples.length) samples.push({ t: 0, motion: 0, scene: 0, bright: 0.5, skin: 0, sx: 0.5, sy: 0.4, mx: 0.5, my: 0.5 });
  }
  return { samples, method: usedDecoder ? 'WebCodecs decode' : 'video seeking' };
}

function buildInterestTrack(samples, sceneCuts) {
  // Subject point: skin-tone centroid (faces/hands) if present, else motion centroid, else upper-center. Heuristic, not face recognition.
  const pts = samples.map((s) => {
    let x = 0.5, y = 0.42, w = 0.2;
    if (s.skin > 0.015) { x = s.sx; y = clamp(s.sy - 0.06, 0.1, 0.9); w = clamp(s.skin * 8, 0.3, 1); }
    else if (s.motion > 0.02) { x = s.mx; y = s.my; w = 0.35; }
    return { t: s.t, x, y, w };
  });
  // forward/backward (zero-phase) weighted smoothing, reset at scene cuts
  const isCut = (t0, t1) => sceneCuts.some((c) => c > t0 && c <= t1);
  const smoothTrack = (alpha) => {
    const out = pts.map((p) => ({ ...p }));
    for (let pass = 0; pass < 2; pass++) {
      const idx = pass === 0 ? [...out.keys()] : [...out.keys()].reverse();
      let px = null, py = null, pt = null;
      for (const i of idx) {
        const p = out[i];
        if (px === null || isCut(Math.min(pt, p.t), Math.max(pt, p.t))) { px = p.x; py = p.y; }
        else { const a = alpha(p.w); px = lerp(px, p.x, a); py = lerp(py, p.y, a); }
        p.x = px; p.y = py; pt = p.t;
      }
    }
    return out;
  };
  const fast = smoothTrack((w) => clamp(0.7 * w, 0.2, 0.75)); // follows the subject: callouts, zoom anchors
  const calm = smoothTrack((w) => 0.25 * w);                    // steady: crop window for horizontal footage
  return fast.map((p, i) => ({ ...p, fx: calm[i].x }));
}
function interestAt(t) {
  const tr = state.analysis && state.analysis.interest;
  if (!tr || !tr.length) return { x: 0.5, y: 0.45, fx: 0.5 };
  if (t <= tr[0].t) return tr[0];
  if (t >= tr[tr.length - 1].t) return tr[tr.length - 1];
  let lo = 0, hi = tr.length - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (tr[m].t <= t) lo = m; else hi = m; }
  const a = tr[lo], b = tr[hi], f = (t - a.t) / (b.t - a.t);
  return { x: lerp(a.x, b.x, f), y: lerp(a.y, b.y, f), fx: lerp(a.fx != null ? a.fx : a.x, b.fx != null ? b.fx : b.x, f) };
}
function motionAt(t) {
  const s = state.analysis && state.analysis.frames;
  if (!s || !s.length) return 0;
  let best = s[0]; for (const x of s) { if (Math.abs(x.t - t) < Math.abs(best.t - t)) best = x; }
  return best.motion;
}

// Beat tracking for user music: onset envelope -> tempo by autocorrelation -> phase alignment.
async function analyzeMusic(buf) {
  const rate = 11025, hop = 256 / rate;
  const full = await renderMono(buf, rate, null);
  const low = await renderMono(buf, rate, [30, 180]);
  const eF = envelopeDb(full, rate, hop), eL = envelopeDb(low, rate, hop);
  const n = eF.length; const on = new Float32Array(n);
  for (let i = 1; i < n; i++) on[i] = Math.max(0, eF[i] - eF[i - 1]) * 0.5 + Math.max(0, eL[i] - eL[i - 1]) * 1.0;
  // normalise and remove local mean
  const m = on.reduce((a, b) => a + b, 0) / n; for (let i = 0; i < n; i++) on[i] = Math.max(0, on[i] - m);
  const minLag = Math.round(60 / 180 / hop), maxLag = Math.round(60 / 70 / hop);
  let bestLag = Math.round(0.5 / hop), bestScore = -1;
  const lim = Math.min(n, Math.round(90 / hop));
  for (let lag = minLag; lag <= maxLag; lag++) {
    let s = 0; for (let i = lag; i < lim; i++) s += on[i] * on[i - lag];
    const bpm = 60 / (lag * hop); const w = Math.exp(-0.5 * Math.pow(Math.log2(bpm / 120) / 0.6, 2));
    s *= w; if (s > bestScore) { bestScore = s; bestLag = lag; }
  }
  let bestPh = 0, bestPs = -1;
  for (let ph = 0; ph < bestLag; ph++) { let s = 0; for (let i = ph; i < n; i += bestLag) s += on[i] + 0.5 * (on[i - 1] || 0) + 0.5 * (on[i + 1] || 0); if (s > bestPs) { bestPs = s; bestPh = ph; } }
  const beats = [];
  for (let i = bestPh; i < n; i += bestLag) {
    let bi = i, bv = on[i];
    for (let j = Math.max(0, i - 2); j <= Math.min(n - 1, i + 2); j++) if (on[j] > bv) { bv = on[j]; bi = j; }
    beats.push({ t: bi * hop, v: bv });
  }
  const mxv = beats.reduce((a, b) => Math.max(a, b.v), 1e-6); beats.forEach((b) => (b.v /= mxv));
  // downbeat phase: which of 4 positions carries most energy
  let dPh = 0, dBest = -1; for (let p = 0; p < 4; p++) { let s = 0; for (let k = p; k < beats.length; k += 4) s += beats[k].v; if (s > dBest) { dBest = s; dPh = p; } }
  beats.forEach((b, k) => (b.down = (k - dPh) % 4 === 0));
  // "drop": biggest rise in 1 s loudness
  const sec = Math.floor(1 / hop); const E = []; for (let i = 0; i + sec < n; i += sec) { let s = 0; for (let j = i; j < i + sec; j++) s += eF[j]; E.push(s / sec); }
  let drop = null, dv = 4; for (let i = 3; i < E.length - 2; i++) { const d = (E[i] + E[i + 1]) / 2 - (E[i - 1] + E[i - 2] + E[i - 3]) / 3; if (d > dv) { dv = d; drop = i; } }
  return { bpm: 60 / (bestLag * hop), beats, drop: drop === null ? null : drop };
}

async function analyzeAll(log, progress) {
  const A = { hop: 0.01 };
  const dur = state.meta.duration;
  progress(0.04, 'Reading the video file…');
  const probe = await probeMedia(state.file);
  if (probe.error) log(`Container probe failed: ${probe.error} (will still try the browser's own decoders)`, 'warn');
  else log(`File: ${probe.container || '?'} · video ${probe.video.map((v) => `${v.codec || '?'} ${v.coded} rot ${v.rotation}° ${v.canDecode ? 'decodable' : 'NOT decodable by WebCodecs'}`).join(', ') || 'none'} · audio ${probe.audio.map((a) => `${a.codec || '?'} ${a.channels}ch ${a.rate} Hz ${a.canDecode ? 'decodable' : 'NOT decodable by WebCodecs'}`).join(', ') || 'none'}`);
  state.probe = probe;
  progress(0.06, 'Decoding original audio…');
  if (!state.origAudio && !state.skipOrigAudio) {
    try { state.origAudio = await decodeAudioFromFile(state.file, log, probe); }
    catch (e) {
      if (e && e.audioDecode) { const err = new Error(errText(e)); err.audioDecode = true; throw err; }
      throw toError(e, 'Audio decoding');
    }
  }
  if (state.origAudio) {
    log(`Original audio: ${state.origAudio.numberOfChannels} ch, ${state.origAudio.sampleRate} Hz, ${state.origAudio.duration.toFixed(1)} s`, 'ok');
    progress(0.15, 'Analyzing speech, pauses and loudness…');
    A.mono16 = await renderMono(state.origAudio, 16000, null);
    const voice = await renderMono(state.origAudio, 16000, [110, 4200]);
    A.env = envelopeDb(voice, 16000, A.hop);
    const dummy = detectSoundRegions(A.env, A.hop, dur, { padPre: 0, padPost: 0, minGap: 0.05 });
    A.noiseDb = dummy.noise; A.loudDb = dummy.loud; A.thrDb = dummy.thr;
    A.rawRegions = dummy.regions;
    A.emphasis = detectEmphasis(A.env, A.hop);
    A.speechMod = speechLikeness(A.env, A.hop, dummy.regions);
    const cov = dummy.regions.reduce((s, r) => s + r.e - r.s, 0) / dur;
    A.soundCoverage = cov;
    A.likelySpeech = A.speechMod > 4.2 && cov > 0.2;
    // speech loudness for normalisation
    let s2 = 0, c2 = 0; const mono = A.mono16;
    for (const r of dummy.regions) { for (let i = Math.floor(r.s * 16000); i < Math.min(mono.length, r.e * 16000); i++) { s2 += mono[i] * mono[i]; c2++; } }
    A.speechRmsDb = c2 ? 10 * Math.log10(s2 / c2 + 1e-12) : -40;
    log(`Sound present ${(cov * 100).toFixed(0)}% of the time · ${A.likelySpeech ? 'speech-like modulation' : 'little speech-like modulation'} · ${A.emphasis.length} emphasis peaks`, 'ok');
  } else {
    log(state.skipOrigAudio ? 'Continuing WITHOUT the original audio (you chose this). Editing uses motion only.' : 'This video has no audio track. Editing uses motion only.', 'warn');
    A.env = new Float32Array(Math.floor(dur / A.hop)).fill(-90); A.rawRegions = []; A.emphasis = []; A.soundCoverage = 0; A.likelySpeech = false; A.speechRmsDb = -40;
  }
  progress(0.35, 'Analyzing motion, scenes and subject position…');
  const fr = await analyzeFrames(state.file, state.url, dur, state.meta.width / state.meta.height, (p) => progress(0.35 + p * 0.45, 'Analyzing motion, scenes and subject position…'));
  A.frames = fr.samples;
  const sc = A.frames.map((s) => s.scene); const scMean = sc.reduce((a, b) => a + b, 0) / Math.max(1, sc.length);
  const scStd = Math.sqrt(sc.reduce((a, b) => a + (b - scMean) ** 2, 0) / Math.max(1, sc.length));
  const scThr = Math.max(0.28, scMean + 3 * scStd);
  A.sceneCuts = A.frames.filter((s) => s.scene > scThr).map((s) => s.t - 0.125);
  A.interest = buildInterestTrack(A.frames, A.sceneCuts);
  A.motionMean = A.frames.reduce((a, s) => a + s.motion, 0) / Math.max(1, A.frames.length);
  A.motionP90 = percentile(A.frames.map((s) => s.motion), 0.9);
  A.skinMean = A.frames.reduce((a, s) => a + s.skin, 0) / Math.max(1, A.frames.length);
  log(`Frames analysed via ${fr.method}: ${A.frames.length} samples · ${A.sceneCuts.length} scene changes · avg motion ${(A.motionMean * 100).toFixed(1)}`, 'ok');
  // heuristic content type (rule-based, not AI)
  const perMin = A.sceneCuts.length / (dur / 60);
  let type = 'vlog', suggest = 'viral';
  if (A.likelySpeech && A.motionMean < 0.03 && dur > 45) { type = 'podcast / interview'; suggest = 'podcast'; }
  else if (A.likelySpeech && A.motionMean < 0.05) { type = 'talking head'; suggest = 'viral'; }
  else if (!A.likelySpeech && A.motionMean > 0.05) { type = 'action / sports'; suggest = 'sports'; }
  else if (!A.likelySpeech && perMin < 6 && A.motionMean < 0.035) { type = A.skinMean < 0.02 ? 'product / object' : 'cinematic b-roll'; suggest = A.skinMean < 0.02 ? 'product' : 'cinematic'; }
  else if (!A.likelySpeech) { type = 'b-roll / montage'; suggest = 'cinematic'; }
  A.contentType = type; A.suggestedStyle = suggest;
  state.analysis = A;
  return A;
}

/* ============================== 5. SPEECH RECOGNITION ============================== */
const TRANSFORMERS_URL = 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.8.1';
const WORKER_SRC = `
import { pipeline, env } from '${TRANSFORMERS_URL}';
env.allowLocalModels = false;
let asr = null, loadedKey = '';
async function load(model, device) {
  const key = model + '|' + device;
  if (asr && loadedKey === key) return asr;
  const progress_callback = (p) => self.postMessage({ type: 'progress', p });
  const tries = device === 'webgpu'
    ? [{ device: 'webgpu', dtype: { encoder_model: 'fp32', decoder_model_merged: 'q4' } }, { device: 'wasm', dtype: 'q8' }, { device: 'wasm' }]
    : [{ device: 'wasm', dtype: 'q8' }, { device: 'wasm' }];
  let err;
  for (const t of tries) {
    try { asr = await pipeline('automatic-speech-recognition', model, { ...t, progress_callback }); loadedKey = key; self.postMessage({ type: 'status', msg: 'Model ready on ' + t.device }); return asr; }
    catch (e) { err = e; self.postMessage({ type: 'status', msg: 'Load attempt failed on ' + t.device + ': ' + (e && e.message || e) }); }
  }
  throw err;
}
self.onmessage = async (e) => {
  const { audio, model, language, device } = e.data;
  try {
    const p = await load(model, device);
    const base = { chunk_length_s: 30, stride_length_s: 5 };
    if (language) { base.language = language; base.task = 'transcribe'; }
    let out, wordLevel = true;
    try { out = await p(audio, { ...base, return_timestamps: 'word' }); }
    catch (err) {
      self.postMessage({ type: 'status', msg: 'Word timestamps unavailable (' + (err && err.message || err) + '), using phrase timestamps' });
      wordLevel = false; out = await p(audio, { ...base, return_timestamps: true });
    }
    self.postMessage({ type: 'result', out, wordLevel });
  } catch (err) { self.postMessage({ type: 'error', message: String(err && err.message || err) }); }
};`;

let asrWorker = null;
async function transcribeLocal(mono16, model, language, onStatus) {
  if (!asrWorker) {
    const blob = new Blob([WORKER_SRC], { type: 'text/javascript' });
    asrWorker = new Worker(URL.createObjectURL(blob), { type: 'module' });
  }
  const device = ('gpu' in navigator) ? 'webgpu' : 'wasm';
  return await new Promise((resolve, reject) => {
    const files = {};
    asrWorker.onmessage = (e) => {
      const d = e.data;
      if (d.type === 'progress') {
        const p = d.p;
        if (p.status === 'progress' && p.file) { files[p.file] = [p.loaded || 0, p.total || 0]; const L = Object.values(files).reduce((a, b) => a + b[0], 0), T = Object.values(files).reduce((a, b) => a + b[1], 0); onStatus(`Downloading model ${(L / 1e6).toFixed(0)} / ${(T / 1e6).toFixed(0)} MB`, T ? L / T : 0); }
        else if (p.status === 'ready') onStatus('Model loaded, recognising speech…', 1);
      } else if (d.type === 'status') onStatus(d.msg);
      else if (d.type === 'result') resolve(d);
      else if (d.type === 'error') reject(new Error(d.message));
    };
    asrWorker.onerror = (e) => reject(new Error('Speech worker failed to start: ' + ((e && e.message) || 'module workers or CDN blocked')));
    const copy = mono16.slice();
    asrWorker.postMessage({ audio: copy, model, language, device }, [copy.buffer]);
  });
}
function whisperChunksToWords(out, wordLevel) {
  const words = [];
  for (const c of out.chunks || []) {
    const [s, e0] = c.timestamp; const e = e0 == null ? s + 0.5 : e0;
    const text = (c.text || '').trim(); if (!text) continue;
    if (wordLevel) { words.push({ w: text, s, e }); continue; }
    pushEstimatedWords(words, text, s, e);
  }
  return words;
}
function pushEstimatedWords(words, text, s, e) {
  // distribute phrase duration across words proportionally to character length (marked as estimated timing)
  const parts = text.split(/\s+/).filter(Boolean); const tot = parts.reduce((a, w) => a + w.length + 1, 0);
  let t = s; for (const w of parts) { const d = (e - s) * (w.length + 1) / tot; words.push({ w, s: t, e: t + d, est: true }); t += d; }
}

const LANG_ISO = { english: 'en', russian: 'ru', uzbek: 'uz', turkish: 'tr', spanish: 'es', german: 'de', french: 'fr', arabic: 'ar' };
async function transcribeOpenAI(mono16, key, language, onStatus) {
  const wav = encodeWav([mono16], 16000);
  if (wav.size > 25e6) throw new Error('Audio too long for the OpenAI API (25 MB limit ≈ 13 min)');
  const fd = new FormData();
  fd.append('file', wav, 'audio.wav'); fd.append('model', 'whisper-1'); fd.append('response_format', 'verbose_json');
  fd.append('timestamp_granularities[]', 'word'); fd.append('timestamp_granularities[]', 'segment');
  if (language && LANG_ISO[language]) fd.append('language', LANG_ISO[language]);
  onStatus('Uploading audio to OpenAI…');
  const r = await fetch('https://api.openai.com/v1/audio/transcriptions', { method: 'POST', headers: { Authorization: 'Bearer ' + key }, body: fd });
  if (!r.ok) throw new Error('OpenAI API error ' + r.status + ': ' + (await r.text()).slice(0, 200));
  const j = await r.json();
  if (j.words && j.words.length) return j.words.map((w) => ({ w: w.word, s: w.start, e: w.end }));
  const words = []; for (const sg of j.segments || []) pushEstimatedWords(words, sg.text.trim(), sg.start, sg.end); return words;
}

function parseSrt(text) {
  const words = []; const blocks = text.replace(/\r/g, '').split(/\n\n+/);
  const ts = (s) => { const m = s.trim().match(/(\d+):(\d+):(\d+)[,.](\d+)/); return m ? (+m[1]) * 3600 + (+m[2]) * 60 + (+m[3]) + (+m[4]) / 1000 : null; };
  for (const b of blocks) {
    const lines = b.split('\n').filter(Boolean); const li = lines.findIndex((l) => l.includes('-->')); if (li < 0) continue;
    const [a, c] = lines[li].split('-->'); const s = ts(a), e = ts(c); if (s == null || e == null) continue;
    const txt = lines.slice(li + 1).join(' ').replace(/<[^>]+>/g, '').trim(); if (txt) pushEstimatedWords(words, txt, s, e);
  }
  return words;
}

// Safety: drop recognised "words" that sit in near-silence (Whisper can hallucinate text on silent audio).
function filterWordsBySound(words) {
  const A = state.analysis; if (!A || !A.env || !state.origAudio) return words;
  const thr = A.noiseDb + Math.max(3, (A.thrDb - A.noiseDb) * 0.4);
  return words.filter((w) => {
    const a = Math.max(0, Math.floor(w.s / A.hop)), b = Math.min(A.env.length, Math.ceil(w.e / A.hop) + 1);
    let mx = -200; for (let i = a; i < b; i++) mx = Math.max(mx, A.env[i]);
    return mx > thr;
  });
}

/* ============================== 6. AUTO EDIT (edit decision list) ============================== */
const FILLER_RE = /^(um+|uh+|uhm+|erm+|er|ah+|hmm+|mm+|eh+|ээ+|эм+|мм+)$/i;
const OK_DOUBLES = new Set(['very', 'really', 'no', 'so', 'yeah', 'yes', 'ha', 'haha', 'bye', 'go', 'that', 'had', 'is', 'да', 'нет', 'ну']);
const STOP = new Set(('a an the and or but if then so of to in on at by for with from as is are was were be been being am do does did have has had ' +
  'i you he she it we they me him her us them my your his its our their this that these those there here what which who whom whose ' +
  'not no yes just very really also too can could will would shall should may might must about into over under again more most some any ' +
  'all each few other such only own same than how when where why up down out off just like get got go going gonna wanna um uh oh ok okay ' +
  'и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне было вот от меня еще нет о из ему теперь когда даже ну').split(/\s+/));
const TRANSITION_DUR = { flash: 0.32, flashsoft: 0.6, whip: 0.34, zoomblast: 0.42, leak: 0.9, glitch: 0.3, crossfade: 0.4, dip: 0.45, wipe: 0.42 };
const normWord = (w) => (w || '').toLowerCase().replace(/[^\p{L}\p{N}']/gu, '');

function mergeIntervals(list, gap = 0) {
  const a = list.filter((r) => r.e > r.s).map((r) => ({ ...r })).sort((x, y) => x.s - y.s); const out = [];
  for (const r of a) { const l = out[out.length - 1]; if (l && r.s - l.e <= gap) l.e = Math.max(l.e, r.e); else out.push(r); }
  return out;
}
function subtractIntervals(keep, cuts) {
  let res = keep.map((r) => ({ ...r }));
  for (const c of cuts) {
    const nx = [];
    for (const r of res) {
      if (c.e <= r.s || c.s >= r.e) { nx.push(r); continue; }
      if (c.s > r.s) nx.push({ s: r.s, e: c.s });
      if (c.e < r.e) nx.push({ s: c.e, e: r.e });
    }
    res = nx;
  }
  return res.filter((r) => r.e - r.s > 0.02);
}

function keywordScore(w) {
  const n = normWord(w.w); if (!n || STOP.has(n) || n.length < 3) return 0;
  let s = n.length >= 6 ? 1 : 0.6;
  if (/\d/.test(n)) s += 1.2;
  if (/[!?]/.test(w.w)) s += 0.5;
  if (/^[A-ZА-Я]{2,}/.test(w.w.trim())) s += 0.4;
  const A = state.analysis;
  if (A && A.env && state.origAudio) {
    const a = Math.floor(w.s / A.hop), b = Math.min(A.env.length, Math.ceil(w.e / A.hop));
    let mx = -200; for (let i = a; i < b; i++) mx = Math.max(mx, A.env[i]);
    s += clamp((mx - (A.loudDb - 6)) / 6, 0, 1);
  }
  return s;
}

function computeSegments() {
  const S = state.settings, st = STYLES[S.style], it = INTENSITY[S.intensity], A = state.analysis, dur = state.meta.duration;
  const words = (state.transcript && state.transcript.words) || [];
  const speechDensity = words.length / dur;
  let mode;
  if (st.highlight) mode = (speechDensity > 1.2 || (!words.length && A.likelySpeech && A.soundCoverage > 0.6)) ? 'speech' : 'highlight';
  else mode = (words.length > 0 || A.likelySpeech) ? 'speech' : 'highlight';
  if (!state.origAudio) mode = 'highlight';
  let keep = []; const cuts = [];
  const wordIv = words.map((w) => ({ s: Math.max(0, w.s - 0.05), e: Math.min(dur, w.e + 0.08) }));
  if (mode === 'speech') {
    const padPre = 0.1 * it.pad, padPost = 0.16 * it.pad, gap = S.minPause > 0 ? S.minPause : st.keepPause * it.pauseMul;
    keep = detectSoundRegions(A.env, A.hop, dur, { padPre, padPost, minGap: gap, thr: S.silAuto ? null : S.silDb }).regions;
    keep = mergeIntervals([...keep, ...wordIv], gap);
    if (S.removeFillers && words.length) {
      for (let i = 0; i < words.length; i++) {
        const w = words[i], p = words[i - 1], n = words[i + 1];
        if (FILLER_RE.test(normWord(w.w))) {
          const cs = Math.max(w.s - 0.03, p ? p.e + 0.01 : 0), ce = Math.min(w.e + 0.03, n ? n.s - 0.01 : dur);
          if (ce > cs + 0.05) cuts.push({ s: cs, e: ce, reason: `filler “${w.w.trim()}”` });
        }
      }
      if (S.intensity !== 'subtle') {
        for (let i = 0; i < words.length; i++) {
          for (let k = 4; k >= 1; k--) {
            if (i + 2 * k > words.length) continue;
            let same = true; for (let j = 0; j < k; j++) if (normWord(words[i + j].w) !== normWord(words[i + k + j].w)) { same = false; break; }
            const first = normWord(words[i].w);
            if (!same || !first) continue;
            if (k === 1 && (first.length < 3 || OK_DOUBLES.has(first))) continue;
            const cs = Math.max(0, words[i].s - 0.03), ce = words[i + k].s - 0.03;
            if (ce > cs + 0.1) { cuts.push({ s: cs, e: ce, reason: `repeated “${words.slice(i, i + k).map((x) => x.w.trim()).join(' ')}”` }); i += k - 1; }
            break;
          }
        }
      }
      keep = subtractIntervals(keep, cuts);
    }
  } else {
    const win = 0.5, nW = Math.ceil(dur / win); const sc = new Float32Array(nW);
    const mMax = Math.max(1e-4, percentile(A.frames.map((f) => f.motion), 0.98));
    const lr = Math.max(1, (A.loudDb || 0) - (A.noiseDb || -60));
    for (let i = 0; i < nW; i++) {
      const t0 = i * win, t1 = t0 + win; let m = 0, scn = 0;
      for (const f of A.frames) if (f.t >= t0 - 0.12 && f.t < t1 + 0.12) { m = Math.max(m, f.motion); scn = Math.max(scn, f.scene); }
      let l = 0; if (state.origAudio) { for (let j = Math.floor(t0 / A.hop); j < Math.min(A.env.length, t1 / A.hop); j++) l = Math.max(l, (A.env[j] - A.noiseDb) / lr); }
      sc[i] = 0.55 * clamp(m / mMax, 0, 1) + 0.35 * clamp(l, 0, 1) + 0.1 * clamp(scn * 2, 0, 1);
    }
    let thr = percentile(Array.from(sc), 1 - it.keepFrac);
    let mark = Array.from(sc, (v) => v >= thr);
    if (S.targetLen) {
      const order = [...sc.keys()].sort((a, b) => sc[b] - sc[a]); mark = new Array(nW).fill(false);
      let tot = 0; for (const i of order) { if (tot >= S.targetLen * 0.85) break; mark[i] = true; tot += win; }
    }
    const regs = []; for (let i = 0; i < nW; i++) if (mark[i]) regs.push({ s: i * win, e: Math.min(dur, (i + 1) * win) });
    keep = mergeIntervals(regs, 0.6).map((r) => ({ s: Math.max(0, r.s - 0.2), e: Math.min(dur, r.e + 0.2) }));
    keep = keep.map((r) => { if (r.e - r.s >= 0.9) return r; const c = (r.s + r.e) / 2; return { s: Math.max(0, c - 0.5), e: Math.min(dur, c + 0.5) }; });
    keep = mergeIntervals([...keep, ...wordIv], 0.1);
  }
  // target length for speech content: drop least interesting phrases (never cuts inside a phrase)
  if (S.targetLen && mode === 'speech') {
    let total = keep.reduce((a, r) => a + r.e - r.s, 0);
    if (total > S.targetLen * 1.1 && keep.length > 1) {
      const scored = keep.map((r, i) => {
        const emph = A.emphasis.filter((p) => p.t >= r.s && p.t < r.e).reduce((a, p) => a + p.v, 0);
        const kw = words.filter((w) => w.s >= r.s && w.e <= r.e).reduce((a, w) => a + keywordScore(w), 0);
        const mo = A.frames.filter((f) => f.t >= r.s && f.t < r.e).reduce((a, f) => a + f.motion, 0);
        return { i, v: (emph + kw * 0.5 + mo * 5) / Math.max(0.5, r.e - r.s) + (i === 0 ? 100 : 0) };
      }).sort((a, b) => a.v - b.v);
      const drop = new Set();
      for (const s of scored) { if (total <= S.targetLen * 1.05) break; if (s.i === 0) continue; drop.add(s.i); total -= keep[s.i].e - keep[s.i].s; }
      keep.forEach((r, i) => { if (drop.has(i)) cuts.push({ s: r.s, e: r.e, reason: 'trimmed for target length' }); });
      keep = keep.filter((_, i) => !drop.has(i));
    }
  }
  if (!keep.length) keep = [{ s: 0, e: dur }];
  // full partition for the Cuts panel
  const segments = []; let t = 0;
  const reasonFor = (s, e) => { const c = cuts.find((c) => c.s < e - 0.01 && c.e > s + 0.01); return c ? c.reason : (mode === 'speech' ? 'pause / silence' : 'low action'); };
  for (const r of keep) {
    if (r.s - t > 0.03) segments.push({ s: t, e: r.s, keep: false, reason: reasonFor(t, r.s) });
    segments.push({ s: Math.max(t, r.s), e: r.e, keep: true, reason: mode === 'speech' ? 'speech / sound' : 'action' });
    t = r.e;
  }
  if (dur - t > 0.03) segments.push({ s: t, e: dur, keep: false, reason: reasonFor(t, dur) });
  return { segments, mode };
}

function clipSrcAt(c, lt) { return c.src0 + c.r0 * lt + (c.r1 - c.r0) * lt * lt / (2 * c.dur); }
function clipInverse(c, s) {
  const x = s - c.src0; if (c.r0 === c.r1) return x / c.r0;
  const a = (c.r1 - c.r0) / (2 * c.dur), b = c.r0; const disc = b * b + 4 * a * x;
  return (-b + Math.sqrt(Math.max(0, disc))) / (2 * a);
}
function clipIndexAt(edit, t) {
  const cl = edit.clips; let lo = 0, hi = cl.length - 1;
  if (t <= 0) return 0; if (t >= edit.duration) return hi;
  while (lo < hi) { const m = (lo + hi + 1) >> 1; if (cl[m].out0 <= t) lo = m; else hi = m - 1; }
  return lo;
}
function srcToOut(edit, s) {
  for (const c of edit.clips) if (s >= c.src0 - 1e-6 && s <= c.srcEnd + 1e-6) return c.out0 + clipInverse(c, s);
  return null;
}
function layoutClips(clips) { let t = 0; clips.forEach((c) => { c.out0 = t; t += c.dur; }); return t; }
function makeClip(s, e, r0, r1, cont, gain = 1) { const len = e - s; return { src0: s, srcEnd: e, r0, r1, dur: r0 === r1 ? len / r0 : 2 * len / (r0 + r1), cont, gain, slow: Math.min(r0, r1) < 0.95 }; }

// BeatCut-style montage: one clip per N beats, taken from the kept footage in story order or spread as highlights.
function beatGrid() {
  if (state.music && state.music.beats.length > 4) return state.music.beats.map((b) => ({ t: b.t, down: b.down, v: b.v }));
  const out = []; for (let t = 0, i = 0; t < 600; t += 0.5, i++) out.push({ t, down: i % 4 === 0, v: 1 }); return out;
}
function buildMontageClips(kept, dur) {
  const S = state.settings; const beats = beatGrid();
  const ivs = beats.slice(1, 40).map((b, i) => b.t - beats[i].t).sort((a, b) => a - b); const iv = ivs[Math.floor(ivs.length / 2)] || 0.5;
  let bpc = S.beatsPerCut === 'auto' ? [1, 2, 4, 8].reduce((a, b) => (Math.abs(b * iv - 1.5) < Math.abs(a * iv - 1.5) ? b : a)) : +S.beatsPerCut;
  while (bpc * iv < 0.45 && bpc < 16) bpc *= 2;
  let k0 = beats.findIndex((b) => b.t >= S.musicOffset - 1e-6); if (k0 < 0) k0 = 0;
  const musicOffset = state.music ? beats[k0].t : 0;
  const musicLeft = state.music ? state.music.buffer.duration - musicOffset : Infinity;
  const maxLen = S.targetLen || 30;
  const keptTotal = kept.reduce((a, r) => a + r.e - r.s, 0);
  const cuts = [0];
  for (let k = k0 + bpc; k < beats.length; k += bpc) { const t = beats[k].t - musicOffset; if (t > maxLen + 1e-6 || t > musicLeft || t > keptTotal + 0.01) break; cuts.push(t); }
  if (cuts.length < 2) cuts.push(Math.min(maxLen, musicLeft, keptTotal));
  const slots = cuts.length - 1, need = cuts[slots]; const clips = [];
  if (S.contentMode === 'highlights' && keptTotal > need * 1.15) {
    const map = (c) => { for (const r of kept) { if (c <= r.e - r.s) return [r.s, r.e, r.s + c]; c -= r.e - r.s; } const l = kept[kept.length - 1]; return [l.s, l.e, l.e]; };
    // pick each slot near the most active moment of its region of the timeline
    for (let i = 0; i < slots; i++) {
      const L = cuts[i + 1] - cuts[i]; let [a, b, s] = map((i + 0.5) / slots * keptTotal); s -= L / 2;
      if (s < a) s = a; if (s + L > b) s = Math.max(a, b - L); if (s + L > dur) s = Math.max(0, dur - L);
      clips.push(makeClip(s, s + L, 1, 1, false));
    }
  } else {
    let ri = 0, cur = kept[0].s;
    for (let i = 0; i < slots; i++) {
      const L = cuts[i + 1] - cuts[i]; let placed = false;
      while (ri < kept.length) {
        const r = kept[ri]; if (cur < r.s) cur = r.s; const rem = r.e - cur;
        if (rem >= L || (rem >= 0.6 * L && cur + L <= dur)) { clips.push(makeClip(cur, cur + L, 1, 1, false)); cur += L; placed = true; break; }
        ri++; if (ri < kept.length) cur = kept[ri].s;
      }
      if (!placed) break;
    }
  }
  if (!clips.length) clips.push(makeClip(0, Math.min(dur, need), 1, 1, false));
  return { clips, musicOffset, bpc };
}

function buildFromSegments(segments, mode) {
  const S = state.settings, st = STYLES[S.style], it = INTENSITY[S.intensity], A = state.analysis, dur = state.meta.duration;
  const words = (state.transcript && state.transcript.words) || [];
  const kept = mergeIntervals(segments.filter((s) => s.keep), 0.001);
  if (st.montage) {
    const m = buildMontageClips(kept.length ? kept : [{ s: 0, e: dur }], dur);
    return finishEdit(m.clips, mode, segments, m.musicOffset, true);
  }
  // speed-ramp peaks (non-speech action only)
  let rampPeaks = [];
  if (S.fx.ramps && st.ramps > 0) {
    const cand = A.frames.filter((f) => f.motion >= A.motionP90 && f.motion > 0.03).sort((a, b) => b.motion - a.motion);
    const want = Math.max(1, Math.round(st.ramps * it.dens * dur / 14));
    for (const f of cand) {
      if (rampPeaks.length >= want) break;
      if (rampPeaks.some((p) => Math.abs(p - f.t) < 3)) continue;
      if (words.some((w) => w.e > f.t - 0.8 && w.s < f.t + 0.8)) continue;
      if (mode === 'speech' && A.rawRegions.some((r) => r.e > f.t - 0.8 && r.s < f.t + 0.8) && A.likelySpeech) continue;
      rampPeaks.push(f.t);
    }
  }
  const slowF = st.ramps >= 1 ? 0.38 : 0.5;
  const clips = [];
  kept.forEach((r) => {
    let pieces = [{ s: r.s, e: r.e, r0: 1, r1: 1 }];
    for (const p of rampPeaks) {
      if (p - 0.6 < r.s || p + 0.6 > r.e) continue;
      const nx = [];
      for (const pc of pieces) {
        if (pc.r0 !== 1 || pc.r1 !== 1 || p - 0.6 < pc.s || p + 0.6 > pc.e) { nx.push(pc); continue; }
        nx.push({ s: pc.s, e: p - 0.5, r0: 1, r1: 1 }, { s: p - 0.5, e: p - 0.3, r0: 1, r1: slowF }, { s: p - 0.3, e: p + 0.3, r0: slowF, r1: slowF },
          { s: p + 0.3, e: p + 0.5, r0: slowF, r1: 1 }, { s: p + 0.5, e: pc.e, r0: 1, r1: 1 });
      }
      pieces = nx;
    }
    pieces.filter((pc) => pc.e - pc.s > 0.01).forEach((pc, k) => clips.push(makeClip(pc.s, pc.e, pc.r0, pc.r1, k > 0, pc.r0 < 1 && pc.r1 < 1 ? 0.85 : 1)));
  });
  return finishEdit(clips, mode, segments, S.musicOffset, false);
}

function finishEdit(clips, mode, segments, musicOffset, montage) {
  const S = state.settings, st = STYLES[S.style], it = INTENSITY[S.intensity], A = state.analysis, dur = state.meta.duration;
  const words = (state.transcript && state.transcript.words) || [];
  // runs (continuous source sections)
  let runs = [];
  const mkRuns = () => {
    runs = []; clips.forEach((c, i) => { if (!c.cont || !runs.length) runs.push({ i0: i, i1: i }); else runs[runs.length - 1].i1 = i; c.run = runs.length - 1; });
    runs.forEach((r) => { r.src0 = clips[r.i0].src0; r.srcEnd = clips[r.i1].srcEnd; r.out0 = clips[r.i0].out0; r.out1 = clips[r.i1].out0 + clips[r.i1].dur; });
  };
  let total = layoutClips(clips); mkRuns();
  // beat-snap cut points for non-speech material (only moves cuts that fall in silence/action, never inside words)
  const beatsOut = state.music && state.music.beats ? state.music.beats.map((b) => ({ t: b.t - musicOffset, v: b.v, down: b.down })).filter((b) => b.t >= -1e-6) : [];
  if (beatsOut.length && st.transRate > 0 && !montage) {
    for (let ri = 0; ri < runs.length - 1; ri++) {
      const last = clips[runs[ri].i1]; if (last.r0 !== 1 || last.r1 !== 1) continue;
      const T = last.out0 + last.dur; let best = null;
      for (const b of beatsOut) if (Math.abs(b.t - T) < 0.22 && (!best || Math.abs(b.t - T) < Math.abs(best.t - T))) best = b;
      if (!best) continue;
      const delta = best.t - T, newEnd = last.srcEnd + delta;
      const nextSrc = clips[runs[ri + 1].i0].src0;
      if (newEnd < last.src0 + 0.3 || newEnd > Math.min(dur, nextSrc - 0.02)) continue;
      if (words.some((w) => w.s < newEnd + 0.05 && w.e > Math.min(newEnd, last.srcEnd) - 0.05)) continue;
      last.srcEnd = newEnd; last.dur = newEnd - last.src0;
      total = layoutClips(clips); mkRuns();
    }
  }
  const edit = { clips, runs, duration: total, mode, segments, beatsOut, musicOffset, montage };
  // jump-cut framing and scene detection per cut
  const cuts = [];
  runs.forEach((r, i) => {
    r.frameScale = 1;
    if (i === 0) return;
    const p = runs[i - 1]; const gap = r.src0 - p.srcEnd;
    const scene = montage || gap > 4 || A.sceneCuts.some((c) => c > p.srcEnd - 0.4 && c < r.src0 + 0.4);
    cuts.push({ t: r.out0, run: i, scene, gap });
    if (S.jumpZoom && st.jumpZoom > 1 && (!scene || montage)) r.frameScale = p.frameScale > 1.001 ? 1 : st.jumpZoom;
  });
  // clip zoom drift (BeatCut "zoom style"): in / out / alternate per section
  runs.forEach((r, i) => {
    const mode = S.drift === 'style' ? (st.kenBurns ? (montage ? 'alternate' : 'in') : 'none') : S.drift;
    const amt = S.drift === 'style' ? st.kenBurns : S.driftAmt;
    r.drift = mode === 'none' ? 0 : mode === 'in' ? amt : mode === 'out' ? -amt : mode === 'random' ? (hash1(i * 3.7) < 0.5 ? amt : -amt) : (i % 2 ? -amt : amt);
  });
  runs.forEach((r) => { const ip = interestAt((r.src0 + r.srcEnd) / 2); r.ax = ip.x; r.ay = ip.y; });
  edit.cuts = cuts;
  // transitions
  const durT = TRANSITION_DUR;
  edit.transitions = []; let lastTr = -9, nSel = 0;
  const pool = S.transType === 'auto' ? st.transitions : S.transType === 'none' ? [] : [S.transType];
  cuts.forEach((c, k) => {
    if (!pool.length) return;
    let rate = (c.scene || mode === 'highlight' ? st.transRate : st.jumpTransRate) * it.dens;
    if (S.transType !== 'auto') rate = Math.max(rate, 0.5);
    rate *= S.transFreq;
    if (hash1(k * 7.31 + 1.7) >= rate || c.t - lastTr < 0.9) return;
    const type = pool[nSel % pool.length]; nSel++;
    edit.transitions.push({ id: 'tr' + k, t: c.t, type, dur: durT[type], dir: hash1(k) > 0.5 ? 1 : -1, enabled: true }); lastTr = c.t;
  });
  // zoom candidates
  const cand = [];
  for (const p of A.emphasis) { const t = srcToOut(edit, p.t); if (t != null) cand.push({ t, v: p.v * 0.9, src: 'emphasis', s: p.t }); }
  for (const w of words) { const k = keywordScore(w); if (k >= 1.2) { const t = srcToOut(edit, w.s); if (t != null) cand.push({ t, v: clamp(k / 3, 0.3, 1), src: 'keyword “' + w.w.trim() + '”', s: w.s }); } }
  if (mode === 'highlight') for (const f of A.frames) if (f.motion >= A.motionP90) { const t = srcToOut(edit, f.t); if (t != null) cand.push({ t, v: clamp(f.motion / Math.max(1e-4, A.motionP90 * 1.5), 0, 1), src: 'motion peak', s: f.t }); }
  for (const b of beatsOut) if (b.down && b.t < total) cand.push({ t: b.t, v: 0.45 * b.v, src: 'music beat', s: null });
  cand.sort((a, b) => b.v - a.v);
  const gap = st.zoomGap / it.dens; const sel = [];
  for (const c of cand) {
    if (c.t < 0.35 || c.t > total - 0.7) continue;
    if (sel.some((s) => Math.abs(s.t - c.t) < gap)) continue;
    sel.push(c);
  }
  sel.sort((a, b) => a.t - b.t);
  edit.zooms = sel.map((c, k) => {
    const punch = st.zoomType === 'punch';
    let t = c.t - (punch ? 0.06 : 0.35);
    const nb = beatsOut.find((b) => Math.abs(b.t - c.t) < 0.12); if (nb) t = nb.t - (punch ? 0.07 : 0.35);
    const attack = punch ? 0.14 : 0.7, release = punch ? 0.35 : 0.9;
    let hold = punch ? clamp(0.45 + c.v * 0.7, 0.45, 1.2) : 0.8;
    const nextScene = cuts.find((x) => x.scene && x.t > t + 0.1);
    if (nextScene) hold = Math.max(0.1, Math.min(hold, nextScene.t - t - attack - release * 0.5));
    const src = c.s != null ? c.s : clipSrcAt(edit.clips[clipIndexAt(edit, c.t)], c.t - edit.clips[clipIndexAt(edit, c.t)].out0);
    const ip = interestAt(src);
    return { id: 'z' + k, t: Math.max(0, t), attack, hold, release, amt: 1 + (st.zoomAmt - 1) * (0.7 + 0.6 * c.v), type: st.zoomType, ax: ip.x, ay: ip.y, enabled: true, why: c.src, v: c.v };
  });
  // shakes, sound effects, beat pulses
  edit.shakes = []; edit.sfx = []; edit.pulses = [];
  const addSfx = (type, t, gain, why) => { if (t + 0.1 < 0 || t > total) return; if (edit.sfx.some((x) => x.type === type && Math.abs(x.t - t) < 0.5)) return; edit.sfx.push({ id: 's' + edit.sfx.length, type, t, gain, why, enabled: true }); };
  for (const tr of edit.transitions) {
    if (st.sfx.whoosh > 0 && ['whip', 'zoomblast', 'glitch', 'leak', 'flash', 'crossfade', 'dip', 'wipe'].includes(tr.type) && hash1(tr.t * 3.1) < st.sfx.whoosh * it.dens)
      addSfx('whoosh', tr.t - 0.33, ['leak', 'crossfade', 'dip'].includes(tr.type) ? 0.5 : 0.85, tr.type + ' transition');
  }
  const strong = edit.zooms.filter((z) => z.type === 'punch').sort((a, b) => b.v - a.v);
  const nImp = Math.round(st.sfx.impact * it.dens * strong.length * 0.5);
  strong.slice(0, nImp).forEach((z) => {
    addSfx('impact', z.t + 0.02, 0.8, 'punch zoom');
    if (st.shake > 0) edit.shakes.push({ t: z.t + 0.04, dur: 0.38, amp: st.shake * (0.6 + 0.4 * z.v), seed: z.t * 13.7 });
  });
  if (mode === 'highlight' && st.shake > 0) {
    for (const f of A.frames) if (f.motion >= A.motionP90 * 1.2) { const t = srcToOut(edit, f.t); if (t != null && !edit.shakes.some((s) => Math.abs(s.t - t) < 1.2)) edit.shakes.push({ t, dur: 0.3, amp: st.shake * 0.5, seed: t * 7.7 }); }
  }
  if (st.sfx.bass > 0) {
    edit.clips.forEach((c) => { if (c.r1 < c.r0) addSfx('bass', c.out0, 0.9, 'slow-motion start'); });
    const first = edit.transitions.find((x) => x.t > 2); if (first && st.sfx.bass >= 0.6) addSfx('bass', first.t, 0.8, 'first big transition');
  }
  let dropOut = null;
  if (state.music && state.music.drop != null) { const d = state.music.drop - musicOffset; if (d > 2.5 && d < total) dropOut = d; }
  if (st.sfx.riser > 0 && total > 7) {
    const target = dropOut || (edit.transitions.find((x) => x.t > 2.6) || {}).t || (edit.zooms.find((z) => z.t > 2.6) || {}).t;
    if (target) { addSfx('riser', target - 2.2, 0.55 * st.sfx.riser, 'build-up into ' + (dropOut ? 'music drop' : 'key moment')); if (dropOut && st.sfx.bass) addSfx('bass', dropOut, 0.9, 'music drop'); }
  }
  edit.sfx.sort((a, b) => a.t - b.t);
  for (const b of beatsOut) if (b.t < total) edit.pulses.push({ t: b.t, down: b.down, glow: (b.down || S.intensity === 'aggressive') ? st.beatPulse * (b.down ? 1 : 0.5) * (0.4 + 0.6 * b.v) : 0 });
  if (montage && st.sfx.impact > 0 && beatsOut.length) addSfx('impact', 0, 0.7, 'first downbeat');
  edit.speech = speechIntervalsOut(edit);
  edit.captions = buildCaptions(edit);
  buildComposition(edit);
  return edit;
}

function speechIntervalsOut(edit) {
  const words = (state.transcript && state.transcript.words) || [];
  const src = words.length ? words.map((w) => ({ s: w.s, e: w.e })) : (state.analysis.likelySpeech ? state.analysis.rawRegions : []);
  const out = [];
  for (const r of src) for (const c of edit.clips) {
    const s = Math.max(r.s, c.src0), e = Math.min(r.e, c.srcEnd);
    if (e > s) out.push({ s: c.out0 + clipInverse(c, s), e: c.out0 + clipInverse(c, e) });
  }
  return mergeIntervals(out, 0.25);
}

function buildCaptions(edit) {
  const words = (state.transcript && state.transcript.words) || []; if (!words.length) return [];
  const cfg = state.settings.cap; const maxW = cfg.words;
  const mw = [];
  for (let wi = 0; wi < words.length; wi++) {
    const w = words[wi];
    const mid = (w.s + w.e) / 2; const m = srcToOut(edit, mid); if (m == null) continue;
    const s = srcToOut(edit, w.s), e = srcToOut(edit, w.e); const half = (w.e - w.s) / 2;
    mw.push({ text: w.w.trim(), s: s != null ? s : m - half, e: e != null ? e : m + half, k: keywordScore(w), wi });
  }
  const groups = []; let cur = null;
  for (let i = 0; i < mw.length; i++) {
    const w = mw[i], prev = mw[i - 1];
    const brk = !cur || cur.words.length >= maxW || (prev && w.s - prev.e > 0.45) || (prev && /[.?!]$/.test(prev.text) && cur.words.length > 0) || (prev && maxW >= 4 && /,$/.test(prev.text) && cur.words.length >= 2);
    if (brk) { cur = { words: [] }; groups.push(cur); }
    cur.words.push(w);
  }
  groups.forEach((g, i) => {
    g.s = g.words[0].s; const nx = groups[i + 1];
    g.e = Math.min(g.words[g.words.length - 1].e + 0.3, nx ? nx.words[0].s : Infinity);
    let best = null; for (const w of g.words) if (w.k >= 1 && (!best || w.k > best.k)) best = w; if (best) best.hl = true;
    g.text = g.words.map((w) => w.text).join(' ');
    g.id = 'c' + i;
  });
  return groups;
}

function runAutoEdit() {
  const { segments, mode } = computeSegments();
  state.edit = buildFromSegments(segments, mode);
  return state.edit;
}
function rebuildFromCurrentSegments() {
  if (!state.edit) return;
  state.edit = buildFromSegments(state.edit.segments, state.edit.mode);
}

/* ============================== 7. SOUND DESIGN & MIX ============================== */
const SFX_RATE = 48000;
let sfxBuffers = null;
function noiseBuffer(ctx, sec) { const b = ctx.createBuffer(1, Math.ceil(sec * ctx.sampleRate), ctx.sampleRate); const d = b.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; return b; }
function tanhCurve(drive) { const n = 1024, c = new Float32Array(n); for (let i = 0; i < n; i++) { const x = (i / (n - 1)) * 2 - 1; c[i] = Math.tanh(x * drive) / Math.tanh(drive); } return c; }
async function synth(sec, build) {
  const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  const ctx = new OAC(2, Math.ceil(sec * SFX_RATE), SFX_RATE); build(ctx); return await ctx.startRendering();
}
async function makeSfx() {
  if (sfxBuffers) return sfxBuffers;
  const whoosh = await synth(0.7, (c) => {
    const n = c.createBufferSource(); n.buffer = noiseBuffer(c, 0.7);
    const bp = c.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 0.9;
    bp.frequency.setValueAtTime(250, 0); bp.frequency.exponentialRampToValueAtTime(2600, 0.33); bp.frequency.exponentialRampToValueAtTime(500, 0.65);
    const g = c.createGain(); g.gain.setValueAtTime(0.0001, 0); g.gain.exponentialRampToValueAtTime(1.0, 0.31); g.gain.exponentialRampToValueAtTime(0.0001, 0.68);
    const pan = c.createStereoPanner ? c.createStereoPanner() : null;
    n.connect(bp); bp.connect(g);
    if (pan) { pan.pan.setValueAtTime(-0.7, 0); pan.pan.linearRampToValueAtTime(0.7, 0.65); g.connect(pan); pan.connect(c.destination); } else g.connect(c.destination);
    n.start(0);
  });
  const impact = await synth(0.9, (c) => {
    const o = c.createOscillator(); o.type = 'sine'; o.frequency.setValueAtTime(120, 0); o.frequency.exponentialRampToValueAtTime(38, 0.35);
    const g = c.createGain(); g.gain.setValueAtTime(1, 0); g.gain.exponentialRampToValueAtTime(0.0008, 0.85);
    const ws = c.createWaveShaper(); ws.curve = tanhCurve(2.5);
    o.connect(g); g.connect(ws); ws.connect(c.destination); o.start(0); o.stop(0.9);
    const n = c.createBufferSource(); n.buffer = noiseBuffer(c, 0.15); const lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 2200;
    const ng = c.createGain(); ng.gain.setValueAtTime(0.7, 0); ng.gain.exponentialRampToValueAtTime(0.001, 0.09);
    n.connect(lp); lp.connect(ng); ng.connect(c.destination); n.start(0);
  });
  const riser = await synth(2.3, (c) => {
    const n = c.createBufferSource(); n.buffer = noiseBuffer(c, 2.3);
    const bp = c.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 2; bp.frequency.setValueAtTime(300, 0); bp.frequency.exponentialRampToValueAtTime(7000, 2.2);
    const g = c.createGain(); g.gain.setValueAtTime(0.0001, 0); g.gain.exponentialRampToValueAtTime(0.8, 2.15); g.gain.linearRampToValueAtTime(0, 2.22);
    n.connect(bp); bp.connect(g); g.connect(c.destination); n.start(0);
    const o = c.createOscillator(); o.type = 'sawtooth'; o.frequency.setValueAtTime(160, 0); o.frequency.exponentialRampToValueAtTime(900, 2.2);
    const lp = c.createBiquadFilter(); lp.type = 'lowpass'; lp.frequency.value = 2500;
    const og = c.createGain(); og.gain.setValueAtTime(0.0001, 0); og.gain.exponentialRampToValueAtTime(0.12, 2.15); og.gain.linearRampToValueAtTime(0, 2.22);
    o.connect(lp); lp.connect(og); og.connect(c.destination); o.start(0); o.stop(2.3);
  });
  const bass = await synth(1.5, (c) => {
    const o = c.createOscillator(); o.type = 'sine'; o.frequency.setValueAtTime(160, 0); o.frequency.exponentialRampToValueAtTime(46, 0.12);
    const g = c.createGain(); g.gain.setValueAtTime(0.0001, 0); g.gain.exponentialRampToValueAtTime(1, 0.008); g.gain.exponentialRampToValueAtTime(0.0005, 1.45);
    const ws = c.createWaveShaper(); ws.curve = tanhCurve(2);
    o.connect(g); g.connect(ws); ws.connect(c.destination); o.start(0); o.stop(1.5);
  });
  sfxBuffers = { whoosh, impact, riser, bass };
  return sfxBuffers;
}

// Renders the complete soundtrack of the edit: original audio (time-mapped incl. speed ramps) + music (ducked) + SFX, limited.
async function renderMix(edit) {
  const S = state.settings; const sr = 48000; const dur = edit.duration;
  const len = Math.max(1, Math.ceil(dur * sr));
  const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
  const ctx = new OAC(2, len, sr);
  const lim = ctx.createDynamicsCompressor();
  lim.threshold.value = -3; lim.knee.value = 2; lim.ratio.value = 20; lim.attack.value = 0.002; lim.release.value = 0.12;
  const master = ctx.createGain(); master.connect(lim); lim.connect(ctx.destination);
  const A = state.analysis;
  if (state.origAudio && S.volOrig > 0) {
    let norm = 1;
    if (S.normalize && A && A.speechRmsDb) norm = clamp(Math.pow(10, (-20 - A.speechRmsDb) / 20), 0.5, 4);
    const clips = edit.clips;
    clips.forEach((c, i) => {
      const next = clips[i + 1];
      const src = ctx.createBufferSource(); src.buffer = state.origAudio;
      const g = ctx.createGain(); const lvl = S.volOrig * norm * c.gain; const fade = 0.006;
      const t0 = c.out0, t1 = c.out0 + c.dur;
      if (!c.cont) { g.gain.setValueAtTime(0, t0); g.gain.linearRampToValueAtTime(lvl, t0 + fade); } else g.gain.setValueAtTime(lvl, t0);
      const endsCut = !next || !next.cont;
      if (endsCut) { g.gain.setValueAtTime(lvl, Math.max(t0 + fade, t1 - fade)); g.gain.linearRampToValueAtTime(0, t1); }
      src.playbackRate.setValueAtTime(c.r0, t0);
      if (c.r1 !== c.r0) src.playbackRate.linearRampToValueAtTime(c.r1, t1);
      src.connect(g); g.connect(master);
      src.start(t0, Math.max(0, c.src0));
      src.stop(t1 + (endsCut ? 0 : 0.003));
    });
  }
  if (state.music && state.music.buffer && S.volMusic > 0) {
    const mb = state.music.buffer;
    const src = ctx.createBufferSource(); src.buffer = mb;
    const mOff = edit.musicOffset != null ? edit.musicOffset : S.musicOffset;
    if (mb.duration < dur + mOff) { src.loop = true; }
    const g = ctx.createGain();
    // gain curve at 100 Hz: base level, ducked during speech, fade in/out
    const base = S.volMusic * 0.55; const duck = S.duck ? 1 - S.duckAmt * 0.85 : 1;
    const n = Math.max(2, Math.ceil(dur * 100)); const curve = new Float32Array(n);
    const target = new Float32Array(n).fill(1);
    if (S.duck) for (const r of edit.speech) { for (let i = Math.max(0, Math.floor((r.s - 0.12) * 100)); i < Math.min(n, Math.ceil((r.e + 0.15) * 100)); i++) target[i] = duck; }
    let v = target[0];
    for (let i = 0; i < n; i++) { const a = target[i] < v ? 0.25 : 0.06; v += (target[i] - v) * a; curve[i] = v * base; }
    for (let i = 0; i < n; i++) { const t = i / 100; curve[i] *= clamp(t / 0.25, 0, 1) * clamp((dur - t) / 1.2, 0, 1); }
    g.gain.setValueCurveAtTime(curve, 0, dur);
    src.connect(g); g.connect(master); src.start(0, mOff % mb.duration); src.stop(dur);
  }
  if (S.volSfx > 0 && edit.sfx.length) {
    const sb = await makeSfx();
    for (const e of edit.sfx) {
      if (!e.enabled) continue;
      const src = ctx.createBufferSource(); src.buffer = sb[e.type]; const g = ctx.createGain(); g.gain.value = S.volSfx * e.gain * 0.8;
      src.connect(g); g.connect(master);
      if (e.t >= 0) src.start(e.t); else src.start(0, -e.t);
    }
  }
  const out = await ctx.startRendering();
  // safety peak normalise (limiter can overshoot slightly)
  let peak = 0; for (let c = 0; c < out.numberOfChannels; c++) { const d = out.getChannelData(c); for (let i = 0; i < d.length; i += 4) peak = Math.max(peak, Math.abs(d[i])); }
  if (peak > 0.99) { const k = 0.98 / peak; for (let c = 0; c < out.numberOfChannels; c++) { const d = out.getChannelData(c); for (let i = 0; i < d.length; i++) d[i] *= k; } }
  out._peak = peak;
  return out;
}

function encodeWav(channels, sr) {
  const nCh = channels.length, n = channels[0].length; const buf = new ArrayBuffer(44 + n * nCh * 2); const v = new DataView(buf);
  const ws = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
  ws(0, 'RIFF'); v.setUint32(4, 36 + n * nCh * 2, true); ws(8, 'WAVE'); ws(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true);
  v.setUint16(22, nCh, true); v.setUint32(24, sr, true); v.setUint32(28, sr * nCh * 2, true); v.setUint16(32, nCh * 2, true); v.setUint16(34, 16, true);
  ws(36, 'data'); v.setUint32(40, n * nCh * 2, true);
  let o = 44; for (let i = 0; i < n; i++) for (let c = 0; c < nCh; c++) { const s = clamp(channels[c][i], -1, 1); v.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true); o += 2; }
  return new Blob([buf], { type: 'audio/wav' });
}
function audioBufferToWav(b) { const ch = []; for (let c = 0; c < b.numberOfChannels; c++) ch.push(b.getChannelData(c)); return encodeWav(ch, b.sampleRate); }

/* ============================== 8. RENDERER (shared by preview and export) ============================== */
function zoomValue(z, t) {
  const l = t - z.t; const { attack: a, hold: h, release: r } = z;
  if (l < 0 || l > a + h + r) return 0;
  if (l < a) return z.type === 'punch' ? easeOutBack(l / a, 2.0) : easeInOutCubic(l / a);
  if (l < a + h) return 1;
  return 1 - easeInOutCubic((l - a - h) / r);
}

// Everything about the frame at output time t, independent of resolution.
function computeView(edit, t, opts = {}) {
  const S = state.settings, st = STYLES[S.style];
  const ci = clipIndexAt(edit, t); const clip = edit.clips[ci]; const run = edit.runs[clip.run];
  const lt = clamp(t - clip.out0, 0, clip.dur); const srcT = clipSrcAt(clip, lt);
  const v = { t, ci, run: clip.run, srcT, scale: 1, ax: 0.5, ay: 0.45, offX: 0, offY: 0, rot: 0, flash: 0, flashCol: [1, 1, 1], leak: 0, leakPh: 0, glitch: 0, ca: 0, glowBoost: 0, expBoost: 0, bypass: !!opts.bypass };
  const ip = interestAt(srcT); v.ax = ip.x; v.ay = ip.y; v.fx = ip.fx != null ? ip.fx : ip.x;
  if (v.bypass) return v;
  v.scale = S.jumpZoom ? run.frameScale : 1;
  if (run.drift) { const q = smoothstep((t - run.out0) / Math.max(0.3, run.out1 - run.out0)); v.scale *= run.drift > 0 ? 1 + run.drift * q : 1 - run.drift * (1 - q); }
  const zg = S.zoomGlobal;
  for (const z of edit.zooms) {
    if (!z.enabled) continue; const zv = zoomValue(z, t); if (zv <= 0) continue;
    v.scale *= Math.max(0.5, 1 + (z.amt - 1) * zg * zv);
    const w = clamp(zv, 0, 1); v.ax = lerp(v.ax, z.ax, w); v.ay = lerp(v.ay, z.ay, w);
  }
  if (S.fx.transitions) for (const tr of edit.transitions) {
    if (!tr.enabled) continue; const hd = tr.dur / 2; const u = (t - tr.t) / hd; if (u <= -1 || u >= 1) continue;
    const k = 1 - Math.abs(u);
    switch (tr.type) {
      case 'flash': v.flash = Math.max(v.flash, Math.pow(k, 2) * 0.95); v.expBoost += 0.25 * k; break;
      case 'flashsoft': v.flash = Math.max(v.flash, Math.pow(k, 1.5) * 0.55); v.flashCol = [1, 0.93, 0.84]; break;
      case 'whip': v.offX += (u < 0 ? -tr.dir * easeInCubic(1 + u) : tr.dir * (1 - easeOutCubic(u))) * 0.5; break;
      case 'zoomblast': v.scale *= 1 + 0.6 * Math.pow(k, 2); v.flash = Math.max(v.flash, 0.22 * Math.pow(k, 3)); break;
      case 'leak': v.leak = Math.max(v.leak, smoothstep(k) * 0.95); v.leakPh = (u + 1) / 2; v.expBoost += 0.08 * k; break;
      case 'glitch': v.glitch = Math.max(v.glitch, k > 0.3 ? 1 : k / 0.3); v.ca += 0.025 * k; break;
      case 'dip': v.flash = Math.max(v.flash, smoothstep(k * 1.15)); v.flashCol = [0, 0, 0]; break;
      case 'wipe':
      case 'crossfade': {
        // second layer: the other side of the cut keeps playing underneath
        const cut = edit.cuts.find((c) => Math.abs(c.t - tr.t) < 1e-3); if (!cut) break;
        const pIn = easeInOutCubic((u + 1) / 2); const prev = edit.runs[cut.run - 1], next = edit.runs[cut.run];
        if (u < 0) v.xf = { run: cut.run, srcT: Math.max(0, next.src0 + (t - tr.t)), mix: pIn };
        else v.xf = { run: cut.run - 1, srcT: Math.min(state.meta.duration - 0.04, prev.srcEnd + (t - tr.t)), mix: 1 - pIn };
        if (tr.type === 'wipe') {
          // directional wipe: incoming shot is revealed behind a moving edge; mix carries the mask side instead of opacity
          const ang = [0, Math.PI / 2, Math.PI, -Math.PI / 2, Math.PI / 4][Math.floor(hash1(tr.t * 3.3) * 5)];
          v.xf.wipe = { dx: Math.cos(ang), dy: Math.sin(ang), p: easeInOutCubic((u + 1) / 2), incomingIsOther: u < 0 };
          v.xf.mix = 1;
        }
        break;
      }
    }
  }
  if (S.fx.shake) for (const sh of edit.shakes) {
    const l = t - sh.t; if (l < 0 || l >= sh.dur) continue; const e = Math.pow(1 - l / sh.dur, 2) * sh.amp;
    v.offX += e * 0.03 * noise1(t * 30 + sh.seed); v.offY += e * 0.03 * noise1(t * 27 + sh.seed + 5); v.rot += e * 0.025 * noise1(t * 21 + sh.seed + 9);
    v.scale *= 1 + 0.06 * e; v.ca += 0.004 * e; v.shakeE = Math.max(v.shakeE || 0, e);
  }
  if (S.fx.beatPulse) for (const p of edit.pulses) {
    const l = t - p.t; if (l < 0 || l > 0.6) continue;
    if (p.glow) { const k = Math.exp(-l * 9) * p.glow; v.glowBoost += 0.5 * k; v.expBoost += 0.05 * k; }
    if (S.pulseZoom) v.scale *= 1 + S.pulseZoom * (p.down ? 1 : 0.55) * Math.exp(-l / 0.11);
  }
  return v;
}

// Affine map from output uv -> source uv
function viewMatrix(v, srcAspect, outW, outH, framing) {
  const outAspect = outW / outH;
  const fit = framing === 'fit' && srcAspect > outAspect * 1.15;
  let cw, ch;
  if (fit) { cw = 1; ch = srcAspect / outAspect; } else if (srcAspect > outAspect) { cw = outAspect / srcAspect; ch = 1; } else { cw = 1; ch = srcAspect / outAspect; }
  const s = Math.max(0.2, v.scale);
  let bx = 0.5, by = 0.5;
  if (!fit && cw < 0.999) bx = clamp(v.fx, cw / 2, 1 - cw / 2);
  let cx = v.ax + (bx - v.ax) / s, cy = v.ay + (by - v.ay) / s;
  if (v.scale <= 1.0001) { cx = bx; cy = by; }
  const hw = cw / (2 * s), hh = ch / (2 * s);
  if (hw < 0.5) cx = clamp(cx, hw, 1 - hw); else cx = 0.5;
  if (hh < 0.5) cy = clamp(cy, hh, 1 - hh); else cy = 0.5;
  cx += v.offX * cw / s; cy += v.offY * ch / s;
  const co = Math.cos(v.rot), si = Math.sin(v.rot), ar = outAspect;
  const a00 = co * cw / s, a01 = -si / ar * cw / s, a10 = si * ar * ch / s, a11 = co * ch / s;
  const tx = cx - (a00 * 0.5 + a01 * 0.5), ty = cy - (a10 * 0.5 + a11 * 0.5);
  return { m: [a00, a10, 0, a01, a11, 0, tx, ty, 1], fit, cw, ch, s, cx, cy, a00, a01, a10, a11, tx, ty };
}
function applyM(M, x, y) { return [M.a00 * x + M.a01 * y + M.tx, M.a10 * x + M.a11 * y + M.ty]; }
function invM(M, sx, sy) { const det = M.a00 * M.a11 - M.a01 * M.a10; const x = sx - M.tx, y = sy - M.ty; return [(M.a11 * x - M.a01 * y) / det, (-M.a10 * x + M.a00 * y) / det]; }

const VS = `#version 300 es
in vec2 p; out vec2 vUv;
void main(){ vUv = p; gl_Position = vec4(p.x*2.0-1.0, 1.0-p.y*2.0, 0.0, 1.0); }`;
const FS = `#version 300 es
precision highp float;
in vec2 vUv; out vec4 o;
uniform sampler2D uSrc; uniform mat3 uM; uniform mat3 uMbg; uniform int uFit;
uniform vec2 uBlur; uniform float uRad; uniform vec2 uRadC; uniform float uLod;
uniform float uExp,uCon,uSat,uWarm,uTint,uSh,uHi,uSplit,uGlow,uVig,uGrain,uSharp,uCA,uFlash,uLeak,uLeakPh,uGlitch,uTime,uBypass;
uniform vec3 uFlashCol; uniform vec2 uOut;
uniform sampler2D uSrc2; uniform mat3 uM2; uniform float uMix2; uniform vec4 uWipe; uniform float uWipeOn; uniform vec3 uWipeCol;
float luma(vec3 c){ return dot(c, vec3(0.2126,0.7152,0.0722)); }
float hash(vec2 p){ return fract(sin(dot(p, vec2(12.9898,78.233))) * 43758.5453); }
void main(){
  vec2 uv = vUv;
  if (uGlitch > 0.0) { float band = floor(uv.y*22.0); float r = hash(vec2(band, floor(uTime*20.0))); if (r > 0.62) uv.x += (r-0.81)*0.16*uGlitch; }
  vec2 s = (uM * vec3(uv,1.0)).xy;
  bool inside = s.x >= 0.0 && s.x <= 1.0 && s.y >= 0.0 && s.y <= 1.0;
  vec3 col;
  if (uFit == 1 && !inside) {
    vec2 b = (uMbg * vec3(uv,1.0)).xy;
    col = (textureLod(uSrc, b, uLod+4.0).rgb*0.6 + textureLod(uSrc, b, uLod+5.0).rgb*0.4) * 0.55;
  } else {
    s = clamp(s, 0.0, 1.0);
    float bl = length(uBlur) + abs(uRad);
    if (bl > 0.0008) {
      vec3 acc = vec3(0.0);
      for (int i = 0; i < 11; i++) { float f = float(i)/10.0 - 0.5; vec2 q = s + f*uBlur + (s-uRadC)*f*uRad; acc += texture(uSrc, clamp(q,0.0,1.0)).rgb; }
      col = acc / 11.0;
    } else col = texture(uSrc, s).rgb;
    if (uMix2 > 0.0) {
      vec2 s2 = clamp((uM2 * vec3(uv,1.0)).xy, 0.0, 1.0); vec3 c2 = texture(uSrc2, s2).rgb;
      if (uWipeOn > 0.5) {
        // d runs 0..1 along the wipe direction; the incoming shot covers d < progress (with a soft edge)
        float d = dot(vUv - 0.5, normalize(uWipe.xy)) / (abs(normalize(uWipe.xy).x) * 0.5 + abs(normalize(uWipe.xy).y) * 0.5) * 0.5 + 0.5;
        float m = 1.0 - smoothstep(uWipe.z - 0.012, uWipe.z + 0.012, d);
        float inc = uWipe.w > 0.5 ? m : 1.0 - m;
        col = mix(col, c2, inc);
        col += uWipeCol * exp(-abs(d - uWipe.z) * 140.0) * step(0.001, uWipe.z) * step(uWipe.z, 0.999);
      } else col = mix(col, c2, uMix2);
    }
    if (uCA > 0.0001) { vec2 d = (s - uRadC) * uCA * 2.0 + vec2(uCA*0.5, 0.0); col.r = texture(uSrc, clamp(s+d,0.0,1.0)).r; col.b = texture(uSrc, clamp(s-d,0.0,1.0)).b; }
    if (uBypass < 0.5) {
      vec3 b1 = textureLod(uSrc, s, uLod+1.0).rgb;
      col += (col - b1) * uSharp * 0.9;
      vec3 g = textureLod(uSrc, s, uLod+2.5).rgb*0.5 + textureLod(uSrc, s, uLod+4.0).rgb*0.5;
      vec3 bright = max(g - 0.55, 0.0) * 2.2;
      col = 1.0 - (1.0 - col) * (1.0 - clamp(bright * uGlow, 0.0, 1.0));
      col += g * uGlow * 0.06;
    }
  }
  if (uBypass < 0.5) {
    col *= pow(2.0, uExp * 2.0);
    col *= vec3(1.0 + uWarm*0.45, 1.0 + uTint*0.3, 1.0 - uWarm*0.45);
    float l = luma(col);
    col += uSh * (1.0 - smoothstep(0.0, 0.5, l)) * 0.6;
    col += uHi * smoothstep(0.5, 1.0, l) * 0.6;
    col = (col - 0.5) * uCon + 0.5;
    l = luma(col);
    col = mix(vec3(l), col, uSat);
    vec3 teal = vec3(-0.05, 0.03, 0.09), orange = vec3(0.09, 0.03, -0.07);
    col += uSplit * mix(teal, orange, smoothstep(0.15, 0.85, l));
    vec2 vc = (vUv - 0.5) * vec2(1.0, 1.25);
    col *= 1.0 - uVig * smoothstep(0.3, 0.95, length(vc)) * 0.85;
    if (uLeak > 0.0) {
      float ph = uLeakPh;
      vec2 c1 = vec2(-0.25 + ph*1.3, 0.15 + 0.35*ph), c2 = vec2(1.2 - ph*1.0, 0.9 - 0.45*ph);
      vec2 d1 = (vUv - c1) * vec2(1.5, 0.8), d2 = (vUv - c2) * vec2(1.3, 0.9);
      vec3 leak = vec3(1.0, 0.48, 0.16) * exp(-dot(d1,d1)*3.0) + vec3(1.0, 0.22, 0.45) * exp(-dot(d2,d2)*3.5) * 0.85;
      col = 1.0 - (1.0 - clamp(col,0.0,1.0)) * (1.0 - clamp(leak * uLeak * 1.2, 0.0, 1.0));
    }
    col = mix(col, uFlashCol, clamp(uFlash, 0.0, 1.0));
    col += (hash(vUv * uOut + fract(uTime*7.13)*100.0) - 0.5) * uGrain * 0.35;
  }
  o = vec4(clamp(col, 0.0, 1.0), 1.0);
}`;

class Renderer {
  constructor(outCanvas) {
    this.out = outCanvas; this.ctx = outCanvas.getContext('2d');
    this.glc = document.createElement('canvas');
    this.gl = null;
    try { this.gl = this.glc.getContext('webgl2', { alpha: false, antialias: false, premultipliedAlpha: false, preserveDrawingBuffer: true }); } catch (e) { this.gl = null; }
    if (this.gl) this.initGL(); else console.warn('WebGL2 unavailable — using basic 2D renderer (no colour grading)');
    this.resize(outCanvas.width, outCanvas.height);
  }
  resize(W, H) { this.W = W; this.H = H; this.out.width = W; this.out.height = H; this.glc.width = W; this.glc.height = H; }
  initGL() {
    const gl = this.gl;
    const sh = (type, src) => { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s)); return s; };
    const pr = gl.createProgram(); gl.attachShader(pr, sh(gl.VERTEX_SHADER, VS)); gl.attachShader(pr, sh(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(pr);
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(pr));
    this.pr = pr; gl.useProgram(pr);
    const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(pr, 'p'); gl.enableVertexAttribArray(loc); gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    this.tex = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, this.tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    this.tex2 = gl.createTexture(); gl.bindTexture(gl.TEXTURE_2D, this.tex2);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([0, 0, 0, 255]));
    this.u = {}; const n = gl.getProgramParameter(pr, gl.ACTIVE_UNIFORMS);
    for (let i = 0; i < n; i++) { const info = gl.getActiveUniform(pr, i); this.u[info.name] = gl.getUniformLocation(pr, info.name); }
    gl.uniform1i(this.u.uSrc, 0); if (this.u.uSrc2) gl.uniform1i(this.u.uSrc2, 1);
  }
  dispose() { try { this.gl && this.gl.getExtension('WEBGL_lose_context') && this.gl.getExtension('WEBGL_lose_context').loseContext(); } catch (e) { } }

  // Draw a full frame for time t from `source` (video element or canvas holding the source frame at v.srcT).
  render(edit, t, source, srcW, srcH, opts = {}) {
    const S = state.settings; const W = this.W, H = this.H, ctx = this.ctx;
    const v = computeView(edit, t, opts);
    const aspect = srcW / srcH;
    const M = viewMatrix(v, aspect, W, H, S.framing);
    let blur = [0, 0], rad = 0;
    if (S.fx.motionBlur && !v.bypass && opts.fps !== 0) {
      const dt = 1 / (opts.fps || 30);
      const vp = computeView(edit, Math.max(0, t - dt), opts);
      if (vp.run === v.run || Math.abs(vp.offX - v.offX) > 0.05) {
        const Mp = viewMatrix(vp, aspect, W, H, S.framing);
        const c0 = applyM(M, 0.5, 0.5), c1 = applyM(Mp, 0.5, 0.5);
        blur = [(c0[0] - c1[0]) * 0.9, (c0[1] - c1[1]) * 0.9];
        rad = (vp.scale / v.scale - 1) * 0.9;
        const bl = Math.hypot(blur[0], blur[1]); if (bl > 0.12) { blur[0] *= 0.12 / bl; blur[1] *= 0.12 / bl; }
        rad = clamp(rad, -0.12, 0.12);
        if (Math.hypot(blur[0], blur[1]) < 0.0015) blur = [0, 0];
        if (Math.abs(rad) < 0.002) rad = 0;
      }
    }
    v.blur = blur; v.rad = rad; v.M = M;
    if (this.gl && source) this.drawGL(v, M, source, srcW, srcH, opts);
    else if (source) this.draw2D(v, M, source, srcW, srcH);
    else { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H); }
    if (!v.bypass) drawOverlays(ctx, edit, t, W, H, v);
    return v;
  }
  drawGL(v, M, source, srcW, srcH, opts) {
    const gl = this.gl, u = this.u, S = state.settings, L = S.look; const W = this.W, H = this.H;
    gl.viewport(0, 0, W, H);
    let mix2 = 0;
    if (v.xf && opts.other && opts.other.source && this.u.uMix2) {
      const o = opts.other; const ip = interestAt(v.xf.srcT);
      const ov = { scale: S.jumpZoom ? state.edit.runs[v.xf.run].frameScale : 1, ax: ip.x, ay: ip.y, fx: ip.fx != null ? ip.fx : ip.x, offX: 0, offY: 0, rot: 0 };
      const M2 = viewMatrix(ov, o.w / o.h, W, H, S.framing);
      gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_2D, this.tex2);
      try { gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, o.source); mix2 = v.xf.mix; } catch (e) { }
      gl.uniformMatrix3fv(this.u.uM2, false, M2.m);
    }
    if (this.u.uMix2) gl.uniform1f(this.u.uMix2, mix2);
    const wp = mix2 > 0 && v.xf && v.xf.wipe;
    if (this.u.uWipeOn) {
      gl.uniform1f(this.u.uWipeOn, wp ? 1 : 0);
      if (wp) { gl.uniform4f(this.u.uWipe, wp.dx, wp.dy, wp.p, wp.incomingIsOther ? 1 : 0); const L = MG_LOOKS[S.style] || MG_LOOKS.viral; const hx = parseInt(L.accent.slice(1), 16); gl.uniform3f(this.u.uWipeCol, ((hx >> 16) & 255) / 255, ((hx >> 8) & 255) / 255, (hx & 255) / 255); }
    }
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, this.tex);
    try { gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source); gl.generateMipmap(gl.TEXTURE_2D); }
    catch (e) { console.warn('texture upload failed', e); }
    gl.uniformMatrix3fv(u.uM, false, M.m);
    const bgv = { ...v, scale: 1, offX: 0, offY: 0, rot: 0 };
    const outAspect = W / H, srcAspect = srcW / srcH; const cw = outAspect / srcAspect;
    gl.uniformMatrix3fv(u.uMbg, false, [cw, 0, 0, 0, 1, 0, 0.5 - cw / 2, 0, 1]);
    gl.uniform1i(u.uFit, M.fit ? 1 : 0);
    gl.uniform2f(u.uBlur, v.blur[0], v.blur[1]); gl.uniform1f(u.uRad, v.rad);
    const rc = applyM(M, 0.5, 0.5); gl.uniform2f(u.uRadC, rc[0], rc[1]);
    gl.uniform1f(u.uLod, Math.max(0, Math.log2(srcH * (M.ch / M.s) / H)));
    const g = (n, val) => { if (u[n]) gl.uniform1f(u[n], val); };
    g('uExp', L.exposure + v.expBoost); g('uCon', L.contrast); g('uSat', L.saturation); g('uWarm', L.warmth); g('uTint', L.tint);
    g('uSh', L.shadows); g('uHi', L.highlights); g('uSplit', L.split); g('uGlow', clamp(L.glow + v.glowBoost, 0, 2)); g('uVig', L.vignette);
    g('uGrain', L.grain); g('uSharp', L.sharpen); g('uCA', v.ca); g('uFlash', v.flash); g('uLeak', v.leak); g('uLeakPh', v.leakPh);
    g('uGlitch', v.glitch); g('uTime', v.t); g('uBypass', v.bypass ? 1 : 0);
    gl.uniform3f(u.uFlashCol, v.flashCol[0], v.flashCol[1], v.flashCol[2]); gl.uniform2f(u.uOut, W, H);
    gl.drawArrays(gl.TRIANGLES, 0, 6);
    this.ctx.drawImage(this.glc, 0, 0, W, H);
  }
  draw2D(v, M, source, srcW, srcH) {
    const ctx = this.ctx, W = this.W, H = this.H;
    ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H);
    // map output corners to source px (ignores rotation in fallback)
    const [x0, y0] = applyM(M, 0, 0), [x1, y1] = applyM(M, 1, 1);
    ctx.drawImage(source, x0 * srcW, y0 * srcH, (x1 - x0) * srcW, (y1 - y0) * srcH, 0, 0, W, H);
    if (v.flash > 0) { ctx.fillStyle = `rgba(255,255,255,${v.flash})`; ctx.fillRect(0, 0, W, H); }
  }
}

/* ---------- text & motion graphics overlays ---------- */
const FONT_W = { 'Montserrat': 900, 'Anton': 400, 'Bebas Neue': 400, 'Poppins': 800, 'Inter': 800, 'Playfair Display': 700 };
function roundRect(ctx, x, y, w, h, r) { ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r); ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); }

/* ============================== 8b. MOTION GRAPHICS COMPOSITION ==============================
   Same data model as HyperFrames compositions (timed clips on tracks, seekable to any frame), but rendered
   natively into the export canvas so it works in iPhone Safari without a server. Every template is a pure
   function of time: preview, scrubbing and frame-by-frame export draw identical frames. */
const MG_LOOKS = {
  viral: { accent: '#ff3d6e', accent2: '#ffe14d', ink: '#ffffff', font: 'Montserrat', weight: 900, title: 'stack', slam: true, slamGap: 5, callout: 'ring', calloutGap: 6, autoTitle: true },
  cinematic: { accent: '#ffcf8a', accent2: '#ffffff', ink: '#ffffff', font: 'Playfair Display', weight: 700, title: 'cinema', slam: false, callout: null, bars: true, autoTitle: false },
  podcast: { accent: '#22d3ee', accent2: '#ffffff', ink: '#ffffff', font: 'Poppins', weight: 800, title: 'clean', slam: false, callout: null, autoTitle: false },
  sports: { accent: '#ffd400', accent2: '#ff2d2d', ink: '#ffffff', font: 'Anton', weight: 400, title: 'sport', slam: true, slamGap: 4, callout: 'track', calloutGap: 3.5, replay: true, autoTitle: true },
  product: { accent: '#7c5cff', accent2: '#ffffff', ink: '#111118', font: 'Inter', weight: 800, title: 'product', slam: false, callout: 'label', calloutGap: 5, autoTitle: false },
  minimal: { accent: '#ffffff', accent2: '#ffffff', ink: '#ffffff', font: 'Inter', weight: 600, title: 'minimal', slam: false, callout: null, autoTitle: false },
  montage: { accent: '#ff3d6e', accent2: '#7c5cff', ink: '#ffffff', font: 'Bebas Neue', weight: 400, title: 'stack', slam: true, slamGap: 4, callout: null, beatFrame: true, autoTitle: true },
};
const MG_NAMES = { title: 'Animated title card', slam: 'Kinetic keyword', callout: 'Subject callout', replay: 'Slow-motion tag', beatFrame: 'Beat frame pulse', bars: 'Cinema bars', lowerThird: 'Lower third', cta: 'Call to action' };

function firstSentenceOut(edit) {
  const out = [];
  for (const g of edit.captions) { for (const w of g.words) { out.push(w.text); if (out.length >= 7 || /[.?!]$/.test(w.text)) return out.join(' ').replace(/[.,]$/, ''); } }
  return out.join(' ');
}
function interestConfidence(srcT) {
  const tr = state.analysis && state.analysis.interest; if (!tr || !tr.length) return 0;
  let best = tr[0]; for (const p of tr) if (Math.abs(p.t - srcT) < Math.abs(best.t - srcT)) best = p;
  return best.w || 0;
}
// Subject position on screen at output time t (null if no subject was detected), computed from the edit itself.
function subjectAtOut(edit, t) {
  const v = computeView(edit, t); if (interestConfidence(v.srcT) < 0.3) return null;
  const M = viewMatrix(v, state.meta.width / state.meta.height, 1080, 1920, state.settings.framing);
  const ip = interestAt(v.srcT); const [x, y] = invM(M, ip.x, ip.y); return { x, y };
}
function bandAvoiding(edit, t0, t1, preferred, alt) {
  for (let t = t0; t <= t1; t += 0.25) { const s = subjectAtOut(edit, Math.min(t, edit.duration - 0.01)); if (s && Math.abs(s.y - preferred) < 0.2) return alt; }
  return preferred;
}
function buildComposition(edit) {
  const S = state.settings, L = MG_LOOKS[S.style] || MG_LOOKS.viral, it = INTENSITY[S.intensity];
  const old = new Map((edit.mg || []).map((c) => [c.key, c.enabled]));
  const clips = [];
  const add = (tpl, start, dur, track, props = {}, key) => {
    start = Math.max(0, start); if (start >= edit.duration - 0.2) return;
    dur = Math.min(dur, edit.duration - start); if (dur < 0.25) return;
    key = key || `${tpl}@${start.toFixed(2)}`;
    clips.push({ id: 'mg' + clips.length, key, tpl, start, dur, track, props, enabled: old.has(key) ? old.get(key) : true });
  };
  const titleText = S.hookText || (S.autoTitle && L.autoTitle && edit.captions.length ? firstSentenceOut(edit) : '');
  let titleEnd = 0;
  if (titleText) {
    const d = L.title === 'cinema' ? 3.4 : 2.7, pref = L.title === 'cinema' ? 0.3 : 0.2;
    add('title', 0.05, d, 4, { text: titleText, look: L.title, fromSpeech: !S.hookText, bandY: bandAvoiding(edit, 0.05, d, pref, L.title === 'cinema' ? 0.56 : 0.5) }, 'title'); titleEnd = 0.05 + d;
  }
  if (L.bars) add('bars', 0, edit.duration, 0, {}, 'bars');
  if (L.slam && edit.captions.length) {
    const cands = [];
    for (const g of edit.captions) for (const w of g.words) if (w.hl && w.k >= 1.2) cands.push(w);
    cands.sort((a, b) => b.k - a.k);
    const chosen = []; const gap = L.slamGap / it.dens;
    for (const w of cands) {
      if (w.s < titleEnd + 0.2 || w.s > edit.duration - 0.8) continue;
      if (chosen.some((c) => Math.abs(c.s - w.s) < gap)) continue;
      chosen.push(w);
    }
    for (const w of chosen) { const d = clamp(w.e - w.s + 0.7, 0.8, 1.4); add('slam', w.s - 0.06, d, 3, { text: w.text.replace(/[.,!?;:]+$/, ''), num: /\d/.test(w.text), bandY: bandAvoiding(edit, w.s, w.s + d, 0.36, 0.58) }); }
  }
  if (L.callout) {
    const zs = edit.zooms.filter((z) => z.enabled).slice().sort((a, b) => b.v - a.v); const picked = [];
    for (const z of zs) {
      if (z.t < titleEnd || picked.some((p) => Math.abs(p.t - z.t) < L.calloutGap / it.dens)) continue;
      const ci = edit.clips[clipIndexAt(edit, z.t + z.attack)]; const srcT = clipSrcAt(ci, clamp(z.t + z.attack - ci.out0, 0, ci.dur));
      if (interestConfidence(srcT) < 0.3) continue; // only when a subject was actually detected
      let label = null;
      if (L.callout === 'label') { const g = edit.captions.find((c) => c.s <= z.t + 0.8 && c.e >= z.t - 0.3); const w = g && g.words.find((x) => x.hl); if (w) label = w.text.replace(/[.,!?;:]+$/, ''); }
      picked.push(z);
      add('callout', z.t + 0.04, z.attack + z.hold + 0.3, 2, { kind: L.callout, ax: z.ax, ay: z.ay, label, side: hash1(z.t * 9.1) > 0.5 ? 1 : -1 });
    }
  }
  if (L.replay) for (const c of edit.clips) if (c.r0 < 0.95 && c.r1 < 0.95) add('replay', c.out0, c.dur + 0.15, 4, { rate: Math.min(c.r0, c.r1) });
  if (L.beatFrame) for (const b of edit.beatsOut) if (b.down && b.t > 0.2) add('beatFrame', b.t, 0.4, 0, { v: b.v });
  if (S.lowerThird) add('lowerThird', 0.8, 4.7, 4, { text: S.lowerThird }, 'lowerThird');
  if (S.ctaText) add('cta', edit.duration - 2.4, 2.4, 4, { text: S.ctaText }, 'cta');
  clips.sort((a, b) => a.track - b.track || a.start - b.start);
  edit.mg = clips;
  return clips;
}

const fade2 = (lt, dur, a, b) => Math.min(clamp(lt / a, 0, 1), clamp((dur - lt) / b, 0, 1));
function mgFont(L, px, italic) { return `${italic ? 'italic ' : ''}${L.weight} ${px}px "${L.font}", Inter, sans-serif`; }

const MG_TEMPLATES = {
  title(ctx, c, lt, e) {
    const { W, H, k, L } = e, P = c.props, look = P.look, dur = c.dur;
    const upper = look !== 'cinema' && look !== 'minimal';
    const text = upper ? P.text.toLocaleUpperCase() : P.text;
    const px = { stack: 92, cinema: 74, sport: 120, product: 72, clean: 64, minimal: 50 }[look] * k;
    ctx.save(); ctx.textBaseline = 'middle'; ctx.font = mgFont(L, px, look === 'cinema');
    const words = text.split(/\s+/).filter(Boolean).map((w, i) => ({ txt: w, w: ctx.measureText(w).width, i }));
    const sp = ctx.measureText(' ').width; const lines = layoutWords(ctx, words, W * (look === 'sport' ? 0.86 : 0.8), sp);
    const lh = px * (look === 'stack' ? 1.32 : 1.2);
    const y0 = H * c.props.bandY - (lines.length - 1) * lh / 2;
    const out = clamp((dur - lt) / 0.35, 0, 1);
    if (look === 'stack') {
      lines.forEach((ln, li) => {
        const y = y0 + li * lh, x0 = (W - ln.w) / 2; const pb = easeOutCubic((lt - li * 0.07) / 0.3), pe = easeInCubic(1 - out);
        const bx = x0 - px * 0.32, bw = ln.w + px * 0.64;
        ctx.fillStyle = li % 2 ? L.accent2 : L.accent;
        ctx.fillRect(bx + bw * pe, y - lh * 0.47, bw * clamp(pb, 0, 1) * (1 - pe), lh * 0.94);
        let x = x0;
        for (const w of ln.words) {
          const p = clamp((lt - 0.12 - w.i * 0.06) / 0.2, 0, 1);
          ctx.save(); ctx.beginPath(); ctx.rect(bx, y - lh * 0.47, bw, lh * 0.94); ctx.clip();
          ctx.globalAlpha = out; ctx.fillStyle = li % 2 ? '#111' : '#fff';
          ctx.fillText(w.txt, x, y + (1 - easeOutBack(p, 2)) * lh * 0.9); ctx.restore(); x += w.w + sp;
        }
      });
    } else if (look === 'cinema') {
      const a = smoothstep(lt / 0.8) * out; ctx.globalAlpha = a; ctx.textAlign = 'center'; ctx.fillStyle = '#fff';
      if ('letterSpacing' in ctx) ctx.letterSpacing = `${lerp(0.35, 0.06, easeOutCubic(lt / 1.6)) * px}px`;
      ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = px * 0.4;
      lines.forEach((ln, li) => ctx.fillText(ln.words.map((w) => w.txt).join(' '), W / 2, y0 + li * lh));
      ctx.shadowBlur = 0; const lw = W * 0.32 * easeInOutCubic(lt / 1.0);
      ctx.fillStyle = L.accent; ctx.fillRect(W / 2 - lw, y0 - lh * 0.85, lw * 2, 2 * k); ctx.fillRect(W / 2 - lw, y0 + (lines.length - 1) * lh + lh * 0.85, lw * 2, 2 * k);
      if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
    } else if (look === 'sport') {
      const pIn = easeOutCubic(lt / 0.25); const sh = lt < 0.4 ? (1 - lt / 0.4) * 10 * k : 0;
      ctx.translate(noise1(lt * 40) * sh, noise1(lt * 37 + 4) * sh);
      const bandH = lines.length * lh + px * 0.4, by = y0 - lh / 2 - px * 0.2;
      ctx.save(); ctx.globalAlpha = out; ctx.transform(1, -0.12, 0, 1, 0, W * 0.06);
      ctx.fillStyle = L.accent2; ctx.fillRect(lerp(-1.2 * W, -0.1 * W, pIn), by + bandH * 0.78, W * 1.2, bandH * 0.22);
      ctx.fillStyle = L.accent; ctx.fillRect(lerp(1.1 * W, -0.1 * W, pIn), by, W * 1.2, bandH * 0.8); ctx.restore();
      ctx.globalAlpha = out; ctx.transform(1, 0, -0.2, 1, 0, 0);
      lines.forEach((ln, li) => { const y = y0 + li * lh; const s = 1 + 0.6 * (1 - easeOutCubic((lt - li * 0.06) / 0.2)); ctx.save(); ctx.translate(W / 2 + y * 0.2, y); ctx.scale(s, s); ctx.lineWidth = px * 0.12; ctx.strokeStyle = '#000'; ctx.textAlign = 'center'; ctx.strokeText(ln.words.map((w) => w.txt).join(' '), 0, 0); ctx.fillStyle = '#111'; ctx.fillText(ln.words.map((w) => w.txt).join(' '), 0, 0); ctx.restore(); });
    } else if (look === 'product') {
      const p = easeOutBack(clamp(lt / 0.45, 0, 1), 1.4), wMax = Math.max(...lines.map((l) => l.w));
      const cw = wMax + px * 1.2, ch = lines.length * lh + px * 0.8, cx = (W - cw) / 2, cy = y0 - lh / 2 - px * 0.4;
      ctx.globalAlpha = out; ctx.translate(0, (1 - p) * 60 * k);
      ctx.fillStyle = 'rgba(255,255,255,0.94)'; roundRect(ctx, cx, cy, cw, ch, px * 0.35); ctx.fill();
      ctx.fillStyle = L.ink; ctx.textAlign = 'center'; lines.forEach((ln, li) => ctx.fillText(ln.words.map((w) => w.txt).join(' '), W / 2, y0 + li * lh));
      ctx.fillStyle = L.accent; ctx.fillRect(cx + px * 0.6, cy + ch - px * 0.32, (cw - px * 1.2) * easeInOutCubic((lt - 0.3) / 0.6), 6 * k);
    } else {
      const a = smoothstep(lt / 0.4) * out; ctx.globalAlpha = a; ctx.fillStyle = '#fff'; ctx.textAlign = 'center';
      ctx.shadowColor = 'rgba(0,0,0,.7)'; ctx.shadowBlur = px * 0.4; const dy = (1 - easeOutCubic(lt / 0.5)) * 24 * k;
      lines.forEach((ln, li) => ctx.fillText(ln.words.map((w) => w.txt).join(' '), W / 2, y0 + li * lh + dy));
      if (look === 'clean') { ctx.shadowBlur = 0; ctx.fillStyle = L.accent; const bw = 90 * k * easeOutCubic(lt / 0.6); ctx.fillRect(W / 2 - bw / 2, y0 + (lines.length - 0.3) * lh, bw, 6 * k); }
    }
    ctx.restore();
  },
  slam(ctx, c, lt, e) {
    const { W, H, k, L, style } = e, P = c.props; const px = (P.num ? 220 : 150) * k;
    const txt = P.text.toLocaleUpperCase(); const pIn = clamp(lt / 0.16, 0, 1), out = clamp((c.dur - lt) / 0.22, 0, 1);
    const s = lerp(2.3, 1, easeOutCubic(pIn)) * lerp(1.12, 1, out);
    ctx.save(); ctx.font = mgFont(L, px, style === 'sports'); ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    let tw = ctx.measureText(txt).width; const fit = Math.min(1, (W * 0.86) / tw);
    const sh = style === 'sports' && lt < 0.35 ? (1 - lt / 0.35) * 14 * k : 0;
    const x = W / 2 + noise1(lt * 45) * sh, y = H * P.bandY + noise1(lt * 41 + 2) * sh;
    // motion echoes trailing the slam-in
    for (let i = 3; i >= 0; i--) {
      const es = s * (1 + i * 0.12 * (1 - pIn)) * fit; const a = (i === 0 ? 1 : 0.18 * (1 - pIn)) * out;
      if (a <= 0.01) continue;
      ctx.save(); ctx.translate(x, y); ctx.scale(es, es); if (style === 'sports') ctx.transform(1, 0, -0.18, 1, 0, 0); ctx.globalAlpha = a;
      if (i === 0) {
        ctx.fillStyle = L.accent; ctx.fillText(txt, 6 * k, 6 * k);
        ctx.lineWidth = px * 0.08; ctx.strokeStyle = '#000'; ctx.lineJoin = 'round'; ctx.strokeText(txt, 0, 0);
        ctx.fillStyle = P.num ? L.accent2 : '#fff';
      } else ctx.fillStyle = L.accent;
      ctx.fillText(txt, 0, 0); ctx.restore();
    }
    ctx.restore();
  },
  callout(ctx, c, lt, e) {
    const { W, H, k, L, v } = e, P = c.props; if (!v.M) return;
    const live = interestAt(v.srcT); const conf = interestConfidence(v.srcT);
    const follow = P.kind === 'track' ? 1 : 0.6;
    const ax = conf > 0.3 ? lerp(P.ax, live.x, follow) : P.ax, ay = conf > 0.3 ? lerp(P.ay, live.y, follow) : P.ay;
    const [sx, sy] = invM(v.M, ax, ay); if (sx < 0.06 || sx > 0.94 || sy < 0.08 || sy > 0.9) return;
    const x = sx * W, y = sy * H, out = clamp((c.dur - lt) / 0.25, 0, 1), R = 150 * k;
    ctx.save(); ctx.globalAlpha = out; ctx.lineCap = 'round'; ctx.shadowColor = 'rgba(0,0,0,.55)'; ctx.shadowBlur = 10 * k;
    if (P.kind === 'ring') {
      const d = easeOutCubic(lt / 0.35); ctx.strokeStyle = L.accent2; ctx.lineWidth = 9 * k;
      const r = R * (1 + 0.05 * Math.sin(lt * 9));
      ctx.beginPath(); ctx.arc(x, y, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * d); ctx.stroke();
      const ang = P.side > 0 ? -0.75 : -2.4, da = easeOutCubic((lt - 0.2) / 0.3);
      const x1 = x + Math.cos(ang) * (r + 190 * k), y1 = y + Math.sin(ang) * (r + 190 * k), x2 = x + Math.cos(ang) * (r + 18 * k), y2 = y + Math.sin(ang) * (r + 18 * k);
      if (da > 0) {
        const ex = lerp(x1, x2, da), ey = lerp(y1, y2, da); ctx.lineWidth = 10 * k; ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(ex, ey); ctx.stroke();
        const a2 = Math.atan2(ey - y1, ex - x1); ctx.fillStyle = L.accent2; ctx.beginPath(); ctx.moveTo(ex + Math.cos(a2) * 26 * k, ey + Math.sin(a2) * 26 * k);
        ctx.lineTo(ex + Math.cos(a2 + 2.5) * 30 * k, ey + Math.sin(a2 + 2.5) * 30 * k); ctx.lineTo(ex + Math.cos(a2 - 2.5) * 30 * k, ey + Math.sin(a2 - 2.5) * 30 * k); ctx.fill();
      }
    } else if (P.kind === 'track') {
      const d = easeOutCubic(lt / 0.25), r = R * lerp(1.6, 1, d); ctx.strokeStyle = L.accent; ctx.lineWidth = 6 * k;
      ctx.setLineDash([22 * k, 14 * k]); ctx.lineDashOffset = -lt * 120 * k; ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);
      for (let i = 0; i < 4; i++) { const a = i * Math.PI / 2 + lt * 1.5; ctx.beginPath(); ctx.moveTo(x + Math.cos(a) * (r - 16 * k), y + Math.sin(a) * (r - 16 * k)); ctx.lineTo(x + Math.cos(a) * (r + 26 * k), y + Math.sin(a) * (r + 26 * k)); ctx.stroke(); }
      const by = y - r - 70 * k + Math.sin(lt * 10) * 10 * k; ctx.fillStyle = L.accent;
      ctx.beginPath(); ctx.moveTo(x - 30 * k, by - 30 * k); ctx.lineTo(x + 30 * k, by - 30 * k); ctx.lineTo(x, by + 14 * k); ctx.fill();
    } else {
      const d = easeOutCubic(lt / 0.3); ctx.fillStyle = L.accent; ctx.beginPath(); ctx.arc(x, y, 12 * k * d, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = '#fff'; ctx.lineWidth = 3 * k; ctx.beginPath(); ctx.arc(x, y, 30 * k * d + 10 * k * Math.sin(lt * 6), 0, Math.PI * 2); ctx.stroke();
      if (P.label) {
        const side = x < W / 2 ? 1 : -1; // point away from the nearest edge
        const lx = x + side * 230 * k, ly = Math.max(y - 170 * k, 120 * k), dl = easeOutCubic((lt - 0.15) / 0.3);
        ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(lerp(x, lx, dl), lerp(y, ly, dl)); ctx.stroke();
        if (dl >= 1) {
          const px = 44 * k; ctx.font = mgFont(L, px); ctx.textBaseline = 'middle'; const tw = ctx.measureText(P.label).width; const pa = easeOutBack(clamp((lt - 0.45) / 0.25, 0, 1), 2);
          const bx = clamp(side > 0 ? lx : lx - tw - px, 20 * k, W - tw - px - 20 * k); ctx.save(); ctx.translate(lx, ly); ctx.scale(pa, pa); ctx.translate(-lx, -ly);
          ctx.fillStyle = '#fff'; roundRect(ctx, bx, ly - px * 0.8, tw + px, px * 1.6, px * 0.3); ctx.fill(); ctx.shadowBlur = 0;
          ctx.fillStyle = L.ink; ctx.fillText(P.label, bx + px / 2, ly); ctx.restore();
        }
      }
    }
    ctx.restore();
  },
  replay(ctx, c, lt, e) {
    const { W, k, L } = e, px = 46 * k, a = fade2(lt, c.dur, 0.2, 0.2); if (a <= 0) return;
    ctx.save(); ctx.globalAlpha = a; ctx.font = mgFont(L, px, true); ctx.textBaseline = 'middle';
    const t1 = 'SLOW-MO', t2 = `${c.props.rate.toFixed(2).replace(/0$/, '')}×`; const w1 = ctx.measureText(t1).width, w2 = ctx.measureText(t2).width;
    const x = 56 * k, y = 150 * k, h = px * 1.6;
    ctx.fillStyle = 'rgba(0,0,0,.6)'; roundRect(ctx, x, y - h / 2, w1 + w2 + px * 2.6, h, h / 2); ctx.fill();
    ctx.fillStyle = Math.floor(lt * 3) % 2 ? L.accent2 : 'rgba(255,45,45,.35)'; ctx.beginPath(); ctx.arc(x + px * 0.75, y, px * 0.28, 0, 7); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.fillText(t1, x + px * 1.3, y); ctx.fillStyle = L.accent; ctx.fillText(t2, x + px * 1.7 + w1, y);
    ctx.restore();
  },
  beatFrame(ctx, c, lt, e) {
    const { W, H, k, L } = e, a = Math.exp(-lt * 9) * (0.5 + 0.5 * (c.props.v || 1)); if (a < 0.02) return;
    const th = 22 * k * a; ctx.save(); ctx.globalAlpha = a; ctx.strokeStyle = L.accent; ctx.lineWidth = th * 2;
    ctx.strokeRect(0, 0, W, H); ctx.globalAlpha = a * 0.8; ctx.strokeStyle = '#fff'; ctx.lineWidth = 4 * k; const m = 40 * k + (1 - a) * 30 * k, l = 90 * k;
    ctx.beginPath(); for (const [dx, dy] of [[0, 0], [1, 0], [1, 1], [0, 1]]) { const cx = dx ? W - m : m, cy = dy ? H - m : m, sx = dx ? -1 : 1, sy = dy ? -1 : 1; ctx.moveTo(cx, cy + sy * l); ctx.lineTo(cx, cy); ctx.lineTo(cx + sx * l, cy); } ctx.stroke();
    ctx.restore();
  },
  bars(ctx, c, lt, e) { const { W, H } = e, h = H * 0.075 * easeInOutCubic(lt / 0.8); ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, h); ctx.fillRect(0, H - h, W, h); },
  lowerThird(ctx, c, lt, e) { drawLowerThird(ctx, c.props.text, lt, e.W, e.H, e.L); },
  cta(ctx, c, lt, e) { drawCta(ctx, c.props.text, lt, e.W, e.H, e.L); },
};

const USER_TEXT_CLIP = (c) => c.tpl === 'lowerThird' || c.tpl === 'cta' || (c.tpl === 'title' && !c.props.fromSpeech);
function drawComposition(ctx, edit, t, W, H, v) {
  if (!edit.mg) return;
  const decor = state.settings.fx.graphics; // the switch hides decorative graphics, never text the user typed
  const S = state.settings; const env = { W, H, k: W / 1080, v, t, edit, L: MG_LOOKS[S.style] || MG_LOOKS.viral, style: S.style };
  for (const c of edit.mg) {
    if (!c.enabled || t < c.start || t >= c.start + c.dur) continue;
    if (!decor && !USER_TEXT_CLIP(c)) continue;
    const tpl = MG_TEMPLATES[c.tpl]; if (!tpl) continue;
    ctx.save();
    try { tpl(ctx, c, t - c.start, env); } catch (err) { console.warn('motion graphic failed', c.tpl, errText(err)); }
    ctx.restore();
  }
}
function slamActive(edit, t) { return !!(edit.mg && state.settings.fx.graphics && edit.mg.some((c) => c.enabled && (c.tpl === 'slam' || (c.tpl === 'title' && c.props.fromSpeech)) && t >= c.start && t < c.start + c.dur)); }

function drawOverlays(ctx, edit, t, W, H, v) {
  const S = state.settings, st = STYLES[S.style], k = W / 1080;
  ctx.save();
  const gfx = S.fx.graphics ? st.graphics : [];
  // tracking brackets around zoom subject
  if (gfx.includes('brackets')) for (const z of edit.zooms) {
    if (!z.enabled) continue; const zv = zoomValue(z, t); if (zv <= 0.05) continue;
    const [sx, sy] = invM(v.M, z.ax, z.ay); if (sx < 0.08 || sx > 0.92 || sy < 0.08 || sy > 0.92) continue;
    const size = 260 * k * (1 + 0.35 * (1 - clamp((t - z.t) / 0.25, 0, 1)));
    const x = sx * W, y = sy * H, b = size / 2, l = size * 0.22;
    ctx.globalAlpha = clamp(zv, 0, 1) * 0.9; ctx.strokeStyle = '#fff'; ctx.lineWidth = 5 * k; ctx.shadowColor = 'rgba(0,0,0,.6)'; ctx.shadowBlur = 8 * k;
    ctx.beginPath();
    for (const [dx, dy] of [[-1, -1], [1, -1], [1, 1], [-1, 1]]) { ctx.moveTo(x + dx * b, y + dy * (b - l)); ctx.lineTo(x + dx * b, y + dy * b); ctx.lineTo(x + dx * (b - l), y + dy * b); }
    ctx.stroke(); ctx.shadowBlur = 0; ctx.globalAlpha = 1;
  }
  // light sweep (product)
  if (gfx.includes('sweep')) for (const ev of [...edit.transitions.filter((x) => x.enabled), ...edit.zooms.filter((z) => z.enabled).map((z) => ({ t: z.t + z.attack }))]) {
    const l = (t - ev.t) / 0.7; if (l < 0 || l > 1) continue;
    const x = lerp(-0.4, 1.4, easeInOutCubic(l)) * W;
    const gr = ctx.createLinearGradient(x - 160 * k, 0, x + 160 * k, 0);
    gr.addColorStop(0, 'rgba(255,255,255,0)'); gr.addColorStop(0.5, 'rgba(255,255,255,0.28)'); gr.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.translate(W / 2, H / 2); ctx.rotate(-0.35); ctx.translate(-W / 2, -H / 2);
    ctx.fillStyle = gr; ctx.fillRect(-W, -H, W * 3, H * 3); ctx.restore();
  }
  // speed lines on impacts (sports)
  if (gfx.includes('speedlines') && v.shakeE > 0.15) {
    ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.strokeStyle = `rgba(255,255,255,${0.35 * clamp(v.shakeE, 0, 1)})`; ctx.lineWidth = 3 * k;
    const cx = W / 2, cy = H / 2, R = Math.hypot(W, H) / 2; const seed = Math.floor(t * 24);
    ctx.beginPath();
    for (let i = 0; i < 36; i++) { const a = hash1(seed * 31 + i) * Math.PI * 2; const r0 = R * (0.55 + 0.2 * hash1(i + seed)); ctx.moveTo(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0); ctx.lineTo(cx + Math.cos(a) * R * 1.1, cy + Math.sin(a) * R * 1.1); }
    ctx.stroke(); ctx.restore();
  }
  if (S.letterbox) { ctx.fillStyle = '#000'; ctx.fillRect(0, 0, W, H * 0.07); ctx.fillRect(0, H * 0.93, W, H * 0.07); }
  // motion-graphics composition (titles, kinetic keywords, callouts, tags, frames, lower third, CTA)
  drawComposition(ctx, edit, t, W, H, v);
  // subtitles (hidden while a kinetic keyword shows the same word big)
  if (S.subsOn && edit.captions.length && !slamActive(edit, t)) {
    const g = edit.captions.find((c) => t >= c.s - 0.02 && t < c.e);
    if (g) drawCaption(ctx, g, t, W, H);
  }
  // progress bar
  if (S.fx.progress) { const p = clamp(t / edit.duration, 0, 1); ctx.fillStyle = 'rgba(255,255,255,0.18)'; ctx.fillRect(0, 0, W, 8 * k); const gr = ctx.createLinearGradient(0, 0, W, 0); gr.addColorStop(0, '#ff3d6e'); gr.addColorStop(1, '#7c5cff'); ctx.fillStyle = gr; ctx.fillRect(0, 0, W * p, 8 * k); }
  ctx.restore();
}

function layoutWords(ctx, words, maxW, spaceW) {
  const lines = []; let cur = { words: [], w: 0 };
  for (const w of words) { const need = cur.words.length ? cur.w + spaceW + w.w : w.w; if (cur.words.length && need > maxW) { lines.push(cur); cur = { words: [], w: 0 }; } cur.w = cur.words.length ? cur.w + spaceW + w.w : w.w; cur.words.push(w); }
  if (cur.words.length) lines.push(cur); return lines;
}

function drawCaption(ctx, g, t, W, H) {
  const c = state.settings.cap, k = W / 1080, style = c.style;
  const base = { viral: 78, cinematic: 58, podcast: 60, sports: 96, minimal: 50 }[style] || 70;
  const px = base * (c.size / 100) * k;
  const fam = c.font; let weight = FONT_W[fam] || 800; if (style === 'minimal' && fam === 'Inter') weight = 600;
  const italic = style === 'cinematic' && fam === 'Playfair Display' ? 'italic ' : '';
  ctx.font = `${italic}${weight} ${px}px "${fam}", Inter, sans-serif`;
  if ('letterSpacing' in ctx) ctx.letterSpacing = style === 'cinematic' ? `${0.03 * px}px` : '0px';
  ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
  const words = g.words.map((w) => { const txt = c.upper ? w.text.toLocaleUpperCase() : w.text; return { ...w, txt, w: ctx.measureText(txt).width }; });
  const spaceW = ctx.measureText(' ').width * (style === 'podcast' ? 1.2 : 1) + (style === 'viral' || style === 'sports' ? px * 0.14 : 0);
  const lines = layoutWords(ctx, words, W * 0.84, spaceW);
  const lh = px * (style === 'podcast' ? 1.35 : 1.18);
  const cy = H * c.pos / 100; const y0 = cy - (lines.length - 1) * lh / 2;
  const pIn = clamp((t - g.s) / (style === 'cinematic' ? 0.3 : 0.16), 0, 1); const pOut = clamp((g.e - t) / 0.18, 0, 1);
  ctx.save();
  let alpha = 1, gscale = 1, dy = 0;
  if (style === 'viral') gscale = 0.65 + 0.35 * easeOutBack(pIn, 2.2);
  else if (style === 'sports') { gscale = 1 + 0.5 * (1 - easeOutCubic(pIn)); alpha = clamp(pIn * 2, 0, 1); }
  else if (style === 'cinematic') { alpha = smoothstep(pIn) * smoothstep(pOut * 1.4); dy = (1 - easeOutCubic(pIn)) * 18 * k; }
  else if (style === 'minimal') alpha = smoothstep(pIn) * smoothstep(pOut * 1.5);
  else if (style === 'podcast') alpha = smoothstep(pIn * 1.5);
  ctx.globalAlpha = alpha;
  ctx.translate(W / 2, cy + dy); ctx.scale(gscale, gscale);
  if (style === 'sports') ctx.transform(1, 0, -0.18, 1, 0, 0);
  ctx.translate(-W / 2, -cy);
  lines.forEach((ln, li) => {
    let x = (W - ln.w) / 2; const y = y0 + li * lh;
    for (const w of ln.words) {
      const active = t >= w.s && t < w.e + 0.06; const spoken = t >= w.s;
      const hl = c.keywords && w.hl;
      let col = c.color; let ws = 1; let jx = 0, jy = 0;
      if (style === 'viral') { if (active) { col = c.hl; ws = 1.12; } else if (hl) col = c.hl; }
      if (style === 'sports') { if (hl || active) col = c.hl; if (active && hl) { jx = noise1(t * 40) * 4 * k; jy = noise1(t * 37 + 3) * 4 * k; } }
      if (style === 'cinematic' || style === 'minimal') { if (hl) col = c.hl; }
      ctx.save();
      const cxw = x + w.w / 2; ctx.translate(cxw + jx, y + jy); ctx.scale(ws, ws); ctx.translate(-cxw, -y);
      if (style === 'podcast') {
        if (active) { ctx.fillStyle = c.hl; roundRect(ctx, x - px * 0.18, y - px * 0.62, w.w + px * 0.36, px * 1.24, px * 0.25); ctx.fill(); col = '#0b0b10'; }
        else { ctx.globalAlpha = alpha * (spoken ? 1 : 0.55); if (hl) col = c.hl; }
        ctx.lineWidth = px * 0.14; ctx.strokeStyle = c.stroke; if (!active) ctx.strokeText(w.txt, x, y);
      } else if (style === 'viral' || style === 'sports') {
        ctx.shadowColor = 'rgba(0,0,0,0.55)'; ctx.shadowBlur = px * 0.22; ctx.shadowOffsetY = px * 0.06;
        ctx.lineWidth = px * (style === 'sports' ? 0.2 : 0.17); ctx.strokeStyle = c.stroke; ctx.strokeText(w.txt, x, y);
        ctx.shadowColor = 'transparent';
      } else {
        ctx.shadowColor = 'rgba(0,0,0,0.75)'; ctx.shadowBlur = px * 0.35; ctx.shadowOffsetY = px * 0.04;
      }
      ctx.fillStyle = col; ctx.fillText(w.txt, x, y);
      ctx.restore();
      x += w.w + spaceW;
    }
  });
  ctx.restore();
  if ('letterSpacing' in ctx) ctx.letterSpacing = '0px';
}

function drawLowerThird(ctx, text, l, W, H, L) {
  const k = W / 1080, px = 40 * k; const p = easeOutCubic(l / 0.5), out = clamp((4.7 - l) / 0.4, 0, 1);
  ctx.save(); ctx.globalAlpha = out; ctx.font = `800 ${px}px "Inter", sans-serif`; ctx.textBaseline = 'middle';
  const tw = ctx.measureText(text).width; const x = 60 * k, y = H * 0.12;
  ctx.fillStyle = 'rgba(10,10,16,0.72)'; roundRect(ctx, x, y - px * 0.9, (tw + px * 1.6) * p, px * 1.8, px * 0.4); ctx.fill();
  ctx.fillStyle = (L && L.accent) || '#ff3d6e'; ctx.fillRect(x, y - px * 0.9, 8 * k, px * 1.8);
  ctx.save(); ctx.beginPath(); ctx.rect(x, y - px, (tw + px * 1.6) * p, px * 2); ctx.clip(); ctx.fillStyle = '#fff'; ctx.fillText(text, x + px * 0.8, y); ctx.restore();
  ctx.restore();
}
function drawCta(ctx, text, l, W, H, L) {
  const k = W / 1080, px = 52 * k; const p = easeOutBack(clamp(l / 0.35, 0, 1), 2);
  ctx.save(); ctx.font = `900 ${px}px "Montserrat", Inter, sans-serif`; ctx.textBaseline = 'middle'; ctx.textAlign = 'center';
  const tw = ctx.measureText(text).width; const y = H * 0.86;
  ctx.translate(W / 2, y); ctx.scale(p, p);
  const gr = ctx.createLinearGradient(-tw / 2, 0, tw / 2, 0); gr.addColorStop(0, (L && L.accent) || '#ff3d6e'); gr.addColorStop(1, (L && L.accent2 && L.accent2 !== '#ffffff' ? L.accent2 : '#7c5cff'));
  ctx.fillStyle = gr; roundRect(ctx, -tw / 2 - px * 0.7, -px * 0.85, tw + px * 1.4, px * 1.7, px * 0.85); ctx.fill();
  ctx.fillStyle = '#fff'; ctx.fillText(text, 0, 0); ctx.restore();
}

/* ============================== 9. PREVIEW PLAYER ============================== */
// Two hidden <video> elements alternate: while one plays the current section, the other is pre-seeked to the next one,
// so jump cuts are instant. Audio comes from the rendered mix (master clock), never from the video elements.
class Player {
  constructor(renderer, vids, audioEl) {
    this.r = renderer; this.vids = vids; this.audio = audioEl;
    this.edit = null; this.t = 0; this.playing = false; this.curRun = -1; this.lastSeek = 0;
    this.mode = 'element'; this.ctx = null; this.ctxStart = 0; this.bypass = false; this.fps = 30;
    this.onTime = null; this.onEnd = null; this.stopAt = null;
  }
  setEdit(edit) { this.edit = edit; this.curRun = -1; this.t = Math.min(this.t, edit.duration); }
  clock() {
    if (this.mode === 'ctx') return this.ctx.currentTime - this.ctxStart;
    const a = this.audio;
    if (a && a.src && !a.paused) {
      const now = performance.now(), at = a.currentTime;
      if (at !== this._lastAT) { this._lastAT = at; this._lastWall = now; }
      return at + Math.min(0.25, (now - this._lastWall) / 1000);
    }
    return this.t0 + (performance.now() - this.wall0) / 1000;
  }
  sourceFor(t) {
    const e = this.edit; const ci = clipIndexAt(e, t); const c = e.clips[ci]; const lt = clamp(t - c.out0, 0, c.dur);
    return { c, run: c.run, srcT: clipSrcAt(c, lt), rate: c.r0 + (c.r1 - c.r0) * (lt / c.dur) };
  }
  syncVideo(t) {
    const { run, srcT, rate } = this.sourceFor(t); const el = this.vids[run % 2]; const now = performance.now();
    if (run !== this.curRun) {
      this.curRun = run;
      if (Math.abs(el.currentTime - srcT) > 0.1) { el.currentTime = srcT; this.lastSeek = now; }
      el.playbackRate = clamp(rate, 0.25, 4);
      if (this.playing) el.play().catch(() => { });
      this.pendingPreload = run + 1;
    } else if (this.playing) {
      if (el.paused) el.play().catch(() => { });
      const drift = el.currentTime - srcT;
      if (Math.abs(drift) > 0.3 && now - this.lastSeek > 700) { el.currentTime = srcT + 0.05; this.lastSeek = now; }
      else { const want = clamp(rate * (1 - clamp(drift * 0.6, -0.12, 0.12)), 0.25, 4); if (Math.abs(el.playbackRate - want) > 0.03) el.playbackRate = want; }
    }
    // preload the next section on the other element once it is no longer needed for a crossfade tail
    const xf = this.bypass ? null : computeView(this.edit, t).xf;
    if (this.pendingPreload != null && !(xf && xf.run < run)) {
      const other = this.vids[this.pendingPreload % 2], nr = this.edit.runs[this.pendingPreload];
      other.pause(); if (nr) other.currentTime = Math.max(0, nr.src0 - this.leadFor(this.pendingPreload));
      this.pendingPreload = null;
    }
    return el;
  }
  leadFor(runIdx) { const r = this.edit.runs[runIdx]; if (!r) return 0; const tr = this.edit.transitions.find((x) => x.enabled && (x.type === 'crossfade' || x.type === 'wipe') && Math.abs(x.t - r.out0) < 1e-3); return tr && state.settings.fx.transitions ? tr.dur / 2 : 0; }
  draw(t, el) {
    if (!(el && el.readyState >= 2 && el.videoWidth)) return;
    const opts = { fps: this.fps, bypass: this.bypass };
    const xf = this.bypass ? null : computeView(this.edit, t).xf;
    if (xf) {
      const o = this.vids[xf.run % 2];
      if (o !== el) {
        if (this.playing && o.paused) o.play().catch(() => { });
        if (Math.abs(o.currentTime - xf.srcT) > 0.35 && !o.seeking) o.currentTime = xf.srcT;
        if (o.readyState >= 2 && o.videoWidth) opts.other = { source: o, w: o.videoWidth, h: o.videoHeight };
      }
    }
    this.r.render(this.edit, t, el, el.videoWidth, el.videoHeight, opts);
  }
  play() {
    if (!this.edit) return;
    if (this.t >= this.edit.duration - 0.05) this.t = 0;
    this.playing = true; this.curRun = -1; this.t0 = this.t; this.wall0 = performance.now(); this._lastAT = null;
    if (this.mode === 'element' && this.audio && this.audio.src) {
      try { this.audio.currentTime = this.t; } catch (e) { }
      const p = this.audio.play(); if (p && p.catch) p.catch((e) => console.warn('audio play blocked', e));
    }
    const loop = () => {
      if (!this.playing) return;
      let t = this.clock();
      if (this.stopAt != null && t >= this.stopAt) { this.stopAt = null; this.pause(); return; }
      if (t >= this.edit.duration) { this.t = this.edit.duration; this.pause(); this.onEnd && this.onEnd(); return; }
      t = Math.max(0, t); this.t = t;
      const el = this.syncVideo(t); this.draw(t, el);
      this.onTime && this.onTime(t);
      this.raf = requestAnimationFrame(loop);
    };
    this.raf = requestAnimationFrame(loop);
  }
  pause() {
    if (this.playing) this.t = clamp(this.clock(), 0, this.edit ? this.edit.duration : 0);
    this.playing = false; cancelAnimationFrame(this.raf);
    if (this.audio) this.audio.pause(); this.vids.forEach((v) => v.pause());
    this.onTime && this.onTime(this.t);
  }
  async seek(t) {
    if (!this.edit) return;
    const was = this.playing; if (was) this.pause();
    this.t = clamp(t, 0, this.edit.duration); this.curRun = -1;
    const { run, srcT } = this.sourceFor(this.t); const el = this.vids[run % 2];
    await new Promise((res) => { const to = setTimeout(res, 1200); const done = () => { clearTimeout(to); el.removeEventListener('seeked', done); res(); }; el.addEventListener('seeked', done); el.currentTime = srcT; });
    this.draw(this.t, el);
    if (this.audio && this.audio.src) try { this.audio.currentTime = this.t; } catch (e) { }
    this.onTime && this.onTime(this.t);
    if (was) this.play();
  }
  redraw() { if (!this.playing && this.edit) { const { run } = this.sourceFor(this.t); this.draw(this.t, this.vids[run % 2]); } }
  async playRange(t0, t1) { await this.seek(t0); this.stopAt = t1; this.play(); }
}

/* ============================== 10. EXPORT ============================== */
function sliceAudio(buf, a, b) {
  const sr = buf.sampleRate; const s = Math.floor(a * sr), e = Math.min(buf.length, Math.floor(b * sr)); const len = Math.max(1, e - s);
  const out = new AudioBuffer({ length: len, numberOfChannels: buf.numberOfChannels, sampleRate: sr });
  for (let c = 0; c < buf.numberOfChannels; c++) out.getChannelData(c).set(buf.getChannelData(c).subarray(s, s + len));
  return out;
}
async function exportCapabilities() {
  await loadMediabunny();
  const res = { webcodecs: false, vcodec: null, acodec: null, decode: false, recorder: null, why: '' };
  if (MB && 'VideoEncoder' in window) {
    try {
      res.vcodec = await MB.getFirstEncodableVideoCodec(['avc', 'hevc', 'vp9', 'av1'], { width: 1080, height: 1920 });
      res.acodec = await MB.getFirstEncodableAudioCodec(['aac', 'opus'], { numberOfChannels: 2, sampleRate: 48000 });
      if (state.file) { const inp = new MB.Input({ source: new MB.BlobSource(state.file), formats: MB.ALL_FORMATS }); const vt = await inp.getPrimaryVideoTrack(); res.decode = !!(vt && await vt.canDecode()); res.inCodec = vt && vt.codec; }
      res.webcodecs = !!(res.vcodec && res.acodec && res.decode);
      if (!res.vcodec) res.why = 'no video encoder'; else if (!res.acodec) res.why = 'no audio encoder (AAC/Opus) in this browser'; else if (!res.decode) res.why = 'cannot decode the source video codec';
    } catch (e) { res.why = errText(e); }
  } else res.why = 'WebCodecs not supported';
  if (window.MediaRecorder && HTMLCanvasElement.prototype.captureStream) {
    const types = ['video/mp4;codecs=avc1.640028,mp4a.40.2', 'video/mp4;codecs=avc1,mp4a.40.2', 'video/mp4', 'video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm'];
    res.recorder = types.find((t) => { try { return MediaRecorder.isTypeSupported(t); } catch (e) { return false; } }) || null;
  }
  return res;
}

async function exportWebCodecs({ W, H, fps, onProgress, signal }) {
  await loadMediabunny(); if (!MB) throw new Error('media library not loaded');
  const edit = state.edit, mix = state.mix;
  const vcodec = await MB.getFirstEncodableVideoCodec(['avc', 'hevc', 'vp9', 'av1'], { width: W, height: H });
  if (!vcodec) throw new Error('no video encoder available');
  const acodec = await MB.getFirstEncodableAudioCodec(['aac', 'opus'], { numberOfChannels: 2, sampleRate: 48000 });
  if (!acodec) throw new Error('no AAC/Opus audio encoder available');
  const webm = (vcodec === 'vp9' || vcodec === 'av1') && acodec === 'opus';
  const input = new MB.Input({ source: new MB.BlobSource(state.file), formats: MB.ALL_FORMATS });
  const vt = await input.getPrimaryVideoTrack();
  if (!vt || !(await vt.canDecode())) throw new Error('this browser cannot decode the source video for frame-accurate export');
  const firstTs = Math.max(0, await vt.getFirstTimestamp().catch(() => 0));
  const cover = Math.max(W / state.meta.width, H / state.meta.height); const sc = Math.min(1, cover * 1.4);
  const even = (x) => Math.max(2, Math.round(x / 2) * 2);
  const sinkOpts = { width: even(state.meta.width * sc), height: even(state.meta.height * sc), fit: 'fill' };
  const sink = new MB.CanvasSink(vt, { ...sinkOpts, poolSize: 3 });
  const sink2 = new MB.CanvasSink(vt, sinkOpts); // random access for crossfade layers
  const canvas = document.createElement('canvas'); canvas.width = W; canvas.height = H;
  const renderer = new Renderer(canvas);
  const output = new MB.Output({ format: webm ? new MB.WebMOutputFormat() : new MB.Mp4OutputFormat({ fastStart: 'in-memory' }), target: new MB.BufferTarget() });
  const vsrc = new MB.CanvasSource(canvas, { codec: vcodec, bitrate: W >= 1080 ? 14e6 : 7e6, keyFrameInterval: 2 });
  output.addVideoTrack(vsrc, { frameRate: fps });
  const asrc = new MB.AudioBufferSource({ codec: acodec, bitrate: 192e3 });
  output.addAudioTrack(asrc);
  await output.start();
  const N = Math.max(1, Math.round(edit.duration * fps));
  function* stamps() { for (let i = 0; i < N; i++) { const t = i / fps; const c = edit.clips[clipIndexAt(edit, t)]; yield firstTs + clipSrcAt(c, clamp(t - c.out0, 0, c.dur)); } }
  let i = 0, audioDone = 0, last = null; const t0 = performance.now();
  const addAudioUntil = async (T) => { T = Math.min(T, edit.duration); while (audioDone < T - 1e-6) { const b = Math.min(edit.duration, audioDone + 1); await asrc.add(sliceAudio(mix, audioDone, b)); audioDone = b; } };
  try {
    for await (const wc of sink.canvasesAtTimestamps(stamps())) {
      if (signal.aborted) throw new DOMException('Export cancelled', 'AbortError');
      const t = i / fps; const c = wc ? wc.canvas : last;
      const opts = { fps }; const xf = computeView(edit, t).xf;
      if (xf) { const w2 = await sink2.getCanvas(firstTs + xf.srcT).catch(() => null); if (w2) opts.other = { source: w2.canvas, w: w2.canvas.width, h: w2.canvas.height }; }
      if (c) renderer.render(edit, t, c, c.width, c.height, opts); else { const x = canvas.getContext('2d'); x.fillStyle = '#000'; x.fillRect(0, 0, W, H); }
      if (wc) last = wc.canvas;
      await vsrc.add(t, 1 / fps);
      await addAudioUntil(t + 1);
      i++;
      if (i % 3 === 0) { const el = (performance.now() - t0) / 1000; onProgress(i / N, `Rendering frame ${i}/${N} · ${(i / el).toFixed(1)} fps · ~${Math.max(0, Math.round((N - i) / Math.max(0.1, i / el)))} s left`); }
    }
    if (i < N) console.warn('decoder yielded fewer frames than requested', i, N);
    await addAudioUntil(edit.duration);
    onProgress(1, 'Finalising MP4…');
    await output.finalize();
  } catch (e) { try { await output.cancel(); } catch (e2) { } renderer.dispose(); throw e; }
  renderer.dispose();
  const type = webm ? 'video/webm' : 'video/mp4';
  return { blob: new Blob([output.target.buffer], { type }), ext: webm ? 'webm' : 'mp4', info: `${vcodec.toUpperCase()} + ${acodec.toUpperCase()}, ${W}×${H}, ${fps} fps, frame-accurate (WebCodecs)` };
}

async function exportRealtime({ W, H, fps, onProgress, signal, vids }) {
  const actx = getAudioCtx(); await actx.resume();
  const caps = await exportCapabilities(); if (!caps.recorder) throw new Error('MediaRecorder with canvas capture is not supported in this browser');
  const canvas = document.createElement('canvas'); canvas.width = W; canvas.height = H;
  canvas.style.cssText = 'position:fixed;left:-9999px;top:0;width:2px;height:2px'; document.body.appendChild(canvas);
  const renderer = new Renderer(canvas);
  const vstream = canvas.captureStream(fps);
  const dest = actx.createMediaStreamDestination();
  const src = actx.createBufferSource(); src.buffer = state.mix; src.connect(dest);
  const stream = new MediaStream([...vstream.getVideoTracks(), ...dest.stream.getAudioTracks()]);
  const rec = new MediaRecorder(stream, { mimeType: caps.recorder, videoBitsPerSecond: W >= 1080 ? 12e6 : 6e6, audioBitsPerSecond: 192000 });
  const chunks = []; rec.ondataavailable = (e) => { if (e.data && e.data.size) chunks.push(e.data); };
  const stopped = new Promise((r) => (rec.onstop = r));
  const player = new Player(renderer, vids, null); player.setEdit(state.edit); player.fps = fps;
  await player.seek(0);
  player.mode = 'ctx'; player.ctx = actx;
  rec.start(1000);
  const startAt = actx.currentTime + 0.25; src.start(startAt); player.ctxStart = startAt;
  player.playing = true; player.curRun = -1;
  const dur = state.edit.duration;
  await new Promise((resolve, reject) => {
    const loop = () => {
      if (signal.aborted) { reject(new DOMException('Export cancelled', 'AbortError')); return; }
      const t = player.clock();
      if (t >= dur + 0.1) { resolve(); return; }
      if (t < 0) { requestAnimationFrame(loop); return; }
      const tt = clamp(t, 0, dur - 1e-3);
      const el = player.syncVideo(tt); player.draw(tt, el);
      onProgress(clamp(t / dur, 0, 1), `Recording in real time ${fmtTime(t)} / ${fmtTime(dur)} — keep this screen open`);
      requestAnimationFrame(loop);
    };
    requestAnimationFrame(loop);
  }).finally(() => { player.playing = false; vids.forEach((v) => v.pause()); try { src.stop(); } catch (e) { } });
  rec.stop(); await stopped;
  renderer.dispose(); canvas.remove();
  const type = caps.recorder.split(';')[0];
  return { blob: new Blob(chunks, { type }), ext: type.includes('mp4') ? 'mp4' : 'webm', info: `${type} via real-time recording, ${W}×${H}` };
}

/* ============================== 11. UI ============================== */
const ui = {};
let player = null, previewRenderer = null, exportAbort = null, wakeLock = null, mixWaveform = null, lastAsrKey = '';
const vids = [$('#vidA'), $('#vidB')];

function log(msg, cls = '') { const d = document.createElement('div'); d.textContent = msg; if (cls) d.className = cls; $('#log').appendChild(d); $('#log').scrollTop = 1e9; console.log('[reels]', msg); }
function setProgress(p, label) { $('#progressBar').style.width = `${Math.round(clamp(p, 0, 1) * 100)}%`; if (label) $('#progressCard h2').textContent = label; }
async function keepAwake(on) {
  try {
    if (on && 'wakeLock' in navigator && !wakeLock) { wakeLock = await navigator.wakeLock.request('screen'); wakeLock.addEventListener('release', () => (wakeLock = null)); }
    if (!on && wakeLock) { await wakeLock.release(); wakeLock = null; }
  } catch (e) { console.warn('wake lock', e); }
}
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && (exportAbort || ui.busy)) keepAwake(true); });

function buildStyleGrid() {
  const g = $('#styleGrid'); g.innerHTML = '';
  for (const [k, s] of Object.entries(STYLES)) {
    const b = document.createElement('button'); b.className = 'style-btn' + (state.settings.style === k ? ' on' : ''); b.dataset.k = k;
    b.innerHTML = `<b>${s.name}</b><span>${s.desc}</span>`;
    b.onclick = () => selectStyle(k, true); g.appendChild(b);
  }
}
function applyStyleDefaults(k) {
  const st = STYLES[k], S = state.settings;
  S.style = k; S.grade = st.grade; S.look = { ...GRADES[st.grade] };
  S.cap = { style: st.captions, ...CAPTION_DEFAULTS[st.captions], keywords: true };
  S.fx.progress = st.progress; S.fx.motionBlur = st.motionBlur; S.pulseZoom = st.pulseZoom; S.drift = 'style';
  if (st.montage && !S.targetLen) S.targetLen = 30;
  syncControlsFromSettings(); saveSettings();
}
async function selectStyle(k, rerun) {
  applyStyleDefaults(k);
  $$('.style-btn').forEach((b) => b.classList.toggle('on', b.dataset.k === k));
  if (rerun && state.edit) { runAutoEdit(); await refreshAll(true); }
}
function syncControlsFromSettings() {
  const S = state.settings;
  $('#fxProgress').checked = S.fx.progress; $('#fxMotionBlur').checked = S.fx.motionBlur;
  $('#gradePreset').value = S.grade; buildLookSliders();
  $('#capStyle').value = S.cap.style; $('#capFont').value = S.cap.font; $('#capSize').value = S.cap.size; $('#capPos').value = S.cap.pos;
  $('#capColor').value = S.cap.color; $('#capHl').value = S.cap.hl; $('#capStroke').value = S.cap.stroke; $('#capUpper').checked = S.cap.upper;
  $('#capWords').value = S.cap.words; $('#capKeywords').checked = S.cap.keywords;
  $('#montageOpts').classList.toggle('hidden', !STYLES[S.style].montage);
  $('#beatsPerCut').value = S.beatsPerCut; $('#contentMode').value = S.contentMode; $('#targetLen').value = String(S.targetLen);
  $('#intensitySeg').querySelectorAll('button').forEach((b) => b.classList.toggle('on', b.dataset.v === S.intensity));
  $('#framing').value = S.framing; $('#removeFillers').checked = S.removeFillers;
  $('#silAuto').checked = S.silAuto; $('#silDb').value = S.silDb; $('#silDb').disabled = S.silAuto; $('#minPause').value = S.minPause;
  $('#drift').value = S.drift; $('#driftAmt').value = S.driftAmt; $('#pulseZoom').value = S.pulseZoom;
  $('#letterbox').checked = S.letterbox; $('#transType').value = S.transType; $('#transFreq').value = S.transFreq;
  $('#volOrig').value = S.volOrig * 100; $('#volMusic').value = S.volMusic * 100; $('#volSfx').value = S.volSfx * 100;
  $('#duck').checked = S.duck; $('#duckAmt').value = S.duckAmt * 100; $('#normalize').checked = S.normalize;
  updateLabels();
}
function updateLabels() {
  const S = state.settings;
  $('#zoomGlobalV').textContent = Math.round(S.zoomGlobal * 100) + '%';
  $('#volOrigV').textContent = Math.round(S.volOrig * 100) + '%'; $('#volMusicV').textContent = Math.round(S.volMusic * 100) + '%'; $('#volSfxV').textContent = Math.round(S.volSfx * 100) + '%';
  $('#duckAmtV').textContent = Math.round(S.duckAmt * 100) + '%'; $('#musicOffsetV').textContent = S.musicOffset.toFixed(1) + ' s';
  $('#silDbV').textContent = S.silAuto ? '(auto)' : S.silDb + ' dB'; $('#minPauseV').textContent = S.minPause > 0 ? S.minPause.toFixed(2) + ' s' : 'auto (style)';
  $('#driftAmtV').textContent = Math.round(S.driftAmt * 100) + '%'; $('#pulseZoomV').textContent = (S.pulseZoom * 100).toFixed(1) + '%';
  $('#transFreqV').textContent = Math.round(S.transFreq * 100) + '%';
  $('#capSizeV').textContent = S.cap.size + '%'; $('#capPosV').textContent = S.cap.pos + '%'; $('#capWordsV').textContent = S.cap.words;
}
function buildLookSliders() {
  const box = $('#lookSliders'); box.innerHTML = ''; const L = state.settings.look;
  for (const [key, label, mn, mx, step] of LOOK_SLIDERS) {
    const wrap = document.createElement('div');
    wrap.innerHTML = `<label class="f">${label} <span>${(+L[key]).toFixed(2)}</span></label><input type="range" min="${mn}" max="${mx}" step="${step}" value="${L[key]}">`;
    const inp = wrap.querySelector('input'), sp = wrap.querySelector('span');
    inp.oninput = () => { L[key] = +inp.value; sp.textContent = (+inp.value).toFixed(2); redraw(); };
    box.appendChild(wrap);
  }
}
function redraw() { if (player) player.redraw(); }

/* ---------- loading ---------- */
async function loadVideo(file) {
  if (player) player.pause();
  if (state.url) URL.revokeObjectURL(state.url);
  Object.assign(state, { file, url: URL.createObjectURL(file), meta: null, origAudio: null, analysis: null, edit: null, mix: null, transcript: null, skipOrigAudio: false, probe: null });
  lastAsrKey = '';
  $('#videoInfo').textContent = 'Loading…';
  ['#previewCard', '#adjustCard', '#exportCard'].forEach((s) => $(s).classList.add('hidden'));
  try {
    for (const v of vids) { v.muted = true; v.defaultMuted = true; v.playsInline = true; v.src = state.url; v.load(); }
    await new Promise((res, rej) => {
      const to = setTimeout(() => rej(new Error('Timed out reading the video (20 s). The file may be stored in iCloud and still downloading — wait and try again.')), 20000);
      vids[0].onloadedmetadata = () => { clearTimeout(to); res(); };
      vids[0].onerror = () => { clearTimeout(to); const me = vids[0].error; rej(new Error(`This browser cannot open this video${me ? ` (MediaError ${me.code}: ${MEDIA_ERR[me.code] || 'unknown'}${me.message ? ' — ' + me.message : ''})` : ''}. Try exporting it from Photos as “Most Compatible”.`)); };
    });
    let d = vids[0].duration;
    if (!isFinite(d)) { vids[0].currentTime = 1e7; await new Promise((r) => (vids[0].ondurationchange = r)); d = vids[0].duration; vids[0].currentTime = 0; }
    state.meta = { duration: d, width: vids[0].videoWidth, height: vids[0].videoHeight };
    const mb = (file.size / 1e6).toFixed(1);
    $('#videoInfo').innerHTML = `<b>${file.name}</b> · ${fmtTime(d)} · ${state.meta.width}×${state.meta.height} · ${mb} MB` + (d > 600 ? ' <span class="badge exp">long video: analysis and export will be slow on phones</span>' : '');
    $('#autoEditBtn').disabled = false;
  } catch (e) { console.error(e); $('#videoInfo').innerHTML = `<span style="color:var(--err)">${escapeHtml(errText(e))}</span>`; $('#autoEditBtn').disabled = true; }
}

async function loadMusic(file) {
  $('#musicInfo').textContent = 'Decoding music…';
  try {
    const buf = await decodeAudioFromFile(file, (m) => console.warn(m));
    if (!buf) throw new Error('could not decode this audio file');
    const beats = await analyzeMusic(buf);
    state.music = { file, buffer: buf, ...beats };
    $('#musicOffset').max = Math.max(0, Math.floor(buf.duration - 5));
    $('#musicInfo').innerHTML = `<b>${file.name}</b> · ${fmtTime(buf.duration)} · ≈${Math.round(beats.bpm)} BPM · ${beats.beats.length} beats detected${beats.drop != null ? ` · drop ≈ ${beats.drop}s` : ''}`;
    $('#musicRemove').classList.remove('hidden');
    if (state.edit) { rebuildFromCurrentSegments(); await refreshAll(true); }
  } catch (e) { state.music = null; $('#musicInfo').innerHTML = `<span style="color:var(--err)">Music error: ${escapeHtml(errText(e))}</span>`; }
}

/* ---------- transcription ---------- */
async function runTranscription(force) {
  const mode = $('#asrMode').value; const A = state.analysis;
  const key = mode + '|' + $('#asrModel').value + '|' + $('#asrLang').value + '|' + (state.pendingSrtName || '');
  if (!force && key === lastAsrKey) return;
  if (mode === 'none') { state.transcript = null; lastAsrKey = key; return; }
  if (!state.origAudio) { log('No audio track — nothing to transcribe.', 'warn'); return; }
  try {
    let words = [], source = '';
    if (mode === 'local') {
      log('Speech recognition (Whisper, on this device)… first run downloads the model.');
      const r = await transcribeLocal(A.mono16, $('#asrModel').value, $('#asrLang').value, (msg, p) => { setProgress(p != null ? 0.82 + p * 0.1 : 0.85, msg); });
      words = whisperChunksToWords(r.out, r.wordLevel); source = 'Whisper (on-device)' + (r.wordLevel ? '' : ', estimated word timing');
    } else if (mode === 'openai') {
      const k = $('#openaiKey').value.trim(); if (!k) throw new Error('enter your OpenAI API key');
      if ($('#rememberKey').checked) localStorage.setItem('reels_openai_key', k); else localStorage.removeItem('reels_openai_key');
      words = await transcribeOpenAI(A.mono16, k, $('#asrLang').value, (m) => setProgress(0.88, m)); source = 'OpenAI Whisper API';
    } else if (mode === 'srt') {
      if (!state.pendingSrt) throw new Error('choose an .srt file first'); words = state.pendingSrt; source = 'imported SRT (estimated word timing)';
    }
    const before = words.length; words = filterWordsBySound(words);
    if (before - words.length > 0) log(`Removed ${before - words.length} recognised words that fell in silence (possible hallucinations).`, 'warn');
    state.transcript = words.length ? { words, source } : null;
    lastAsrKey = key;
    log(words.length ? `Subtitles: ${words.length} words from ${source}.` : 'Speech recognition returned no words.', words.length ? 'ok' : 'warn');
  } catch (e) {
    log('Subtitles failed: ' + errText(e) + ' — continuing without subtitles.', 'err');
  }
}

/* ---------- AUTO EDIT ---------- */
async function doAutoEdit() {
  if (!state.file || ui.busy) return;
  ui.busy = true; $('#autoEditBtn').disabled = true;
  const actx = getAudioCtx(); actx.resume().catch(() => { });
  for (const v of vids) { const p = v.play(); if (p && p.then) p.then(() => v.pause()).catch(() => { }); }
  $('#progressCard').classList.remove('hidden'); $('#log').innerHTML = ''; $('#analysisChips').innerHTML = '';
  await keepAwake(true);
  const t0 = performance.now();
  try {
    log(`Browser: ${navigator.userAgent.replace(/^Mozilla\/5\.0 /, '')}`);
    log(`Capabilities: VideoDecoder ${'VideoDecoder' in window ? '✓' : '✗'} · AudioDecoder ${'AudioDecoder' in window ? '✓' : '✗'} · VideoEncoder ${'VideoEncoder' in window ? '✓' : '✗'} · AudioEncoder ${'AudioEncoder' in window ? '✓' : '✗'} · WebGL2 ${document.createElement('canvas').getContext('webgl2') ? '✓' : '✗'} · MediaRecorder ${'MediaRecorder' in window ? '✓' : '✗'} · media library ${MB ? '✓' : (await loadMediabunny()) ? '✓' : '✗ (vendor/mediabunny.min.mjs missing?)'}`);
    log(`Video: ${state.file.name} · ${state.file.type || 'unknown type'} · ${(state.file.size / 1e6).toFixed(1)} MB · ${fmtTime(state.meta.duration)} · ${state.meta.width}×${state.meta.height}`);
    setProgress(0.02, 'Checking that the video decodes…');
    await verifyVideoFrames();
    if (!state.analysis) await analyzeAll(log, setProgress);
    showAnalysisChips();
    setProgress(0.82, 'Subtitles…'); await runTranscription(false);
    setProgress(0.93, 'Building the edit…');
    runAutoEdit();
    const e = state.edit;
    log(`Edit: ${fmtTime(state.meta.duration)} → ${fmtTime(e.duration)} · ${e.runs.length} sections · ${e.zooms.length} zooms · ${e.transitions.length} transitions · ${e.sfx.length} sound FX · ${e.captions.length} captions`, 'ok');
    setProgress(0.96, 'Mixing audio…');
    await refreshAll(true);
    setProgress(1, `Done in ${((performance.now() - t0) / 1000).toFixed(1)} s — preview below`);
    $('#previewCard').classList.remove('hidden'); $('#adjustCard').classList.remove('hidden'); $('#exportCard').classList.remove('hidden');
    updateExportSupport();
    await player.seek(0);
    $('#previewCard').scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (e) {
    console.error('AUTO EDIT failed', e);
    log('Error: ' + errText(e), 'err');
    const frames = e && e.stack ? String(e.stack).split('\n').map((l) => l.trim()).filter((l) => /^at |@/.test(l)).slice(0, 3) : [];
    if (frames.length) log('Where: ' + frames.join(' ← '), 'warn');
    if (e && e.audioDecode) {
      setProgress(1, 'Original audio could not be decoded');
      log('The edit was stopped so it does not silently lose your sound. Details for each decoding route are listed above. You can try again, export the clip from Photos as “Most Compatible”, or continue without the original audio.', 'warn');
      const b = document.createElement('button'); b.className = 'btn small'; b.textContent = 'Continue without original audio';
      b.onclick = () => { state.skipOrigAudio = true; b.remove(); doAutoEdit(); };
      $('#log').appendChild(b);
    } else setProgress(1, 'Something went wrong — details below');
  } finally { ui.busy = false; $('#autoEditBtn').disabled = false; keepAwake(false); }
}

// Make sure the hidden player elements actually produce frames (iOS only decodes after a tap-initiated play()).
async function verifyVideoFrames() {
  for (const [i, v] of vids.entries()) {
    if (v.readyState >= 2 && v.videoWidth) continue;
    const ok = await new Promise((res) => {
      const to = setTimeout(() => res(false), 8000);
      const done = () => { clearTimeout(to); res(true); };
      v.addEventListener('loadeddata', done, { once: true }); v.addEventListener('seeked', done, { once: true });
      try { v.currentTime = Math.min(0.05, (state.meta.duration || 1) / 2); } catch (e) { }
    });
    if (!ok && !(v.readyState >= 2)) {
      const me = v.error;
      throw new Error(`The browser could not decode video frames (player ${i + 1}, readyState ${v.readyState}${me ? `, MediaError ${me.code}: ${MEDIA_ERR[me.code] || ''} ${me.message || ''}` : ''}). Try exporting the clip from Photos as “Most Compatible” (H.264).`);
    }
  }
  log(`Video frames decode OK (${vids[0].videoWidth}×${vids[0].videoHeight}).`, 'ok');
}
function showAnalysisChips() {
  const A = state.analysis; const c = $('#analysisChips'); c.innerHTML = '';
  const chip = (t, cls = '') => { const s = document.createElement('span'); s.className = 'badge ' + cls; s.textContent = t; c.appendChild(s); return s; };
  chip('Detected (rule-based): ' + A.contentType);
  if (A.suggestedStyle !== state.settings.style) { const b = document.createElement('button'); b.className = 'btn small'; b.textContent = `Try suggested style: ${STYLES[A.suggestedStyle].name}`; b.onclick = () => selectStyle(A.suggestedStyle, true); c.appendChild(b); }
  if (state.music) chip(`Music ≈ ${Math.round(state.music.bpm)} BPM`);
}

async function refreshAll(remix) {
  const e = state.edit; if (!e) return;
  if (!previewRenderer) { previewRenderer = new Renderer($('#previewCanvas')); applyPreviewSize(); }
  if (!player) {
    player = new Player(previewRenderer, vids, $('#previewAudio'));
    player.onTime = (t) => { $('#timeLabel').textContent = `${fmtTime(t)} / ${fmtTime(state.edit.duration)}`; if (!ui.scrubbing) $('#scrub').value = Math.round(t / state.edit.duration * 1000); drawTimeline(); };
    player.onEnd = () => { $('#playBtn').textContent = '▶ Play'; };
  }
  const wasPlaying = player.playing; if (wasPlaying) player.pause();
  player.setEdit(e);
  $('#editSummary').textContent = `${fmtTime(e.duration)} (from ${fmtTime(state.meta.duration)})`;
  fillCutList(); fillZoomList(); fillTransList(); fillSfxList(); fillCapList(); fillMgList();
  if (remix) await remixAudio();
  drawTimeline(); player.redraw();
  if (wasPlaying) { player.play(); }
}

async function remixAudio() {
  if (!state.edit) return;
  const t = player ? player.t : 0; const was = player && player.playing; if (was) player.pause();
  state.mix = await renderMix(state.edit);
  const a = $('#previewAudio'); if (a.src) URL.revokeObjectURL(a.src);
  a.src = URL.createObjectURL(audioBufferToWav(state.mix)); a.load();
  computeWaveform();
  if (player) { player.t = t; if (was) player.play(); }
}
const remixSoon = debounce(() => remixAudio(), 350);

/* ---------- timeline ---------- */
function computeWaveform() {
  const m = state.mix; const n = 700; const out = new Float32Array(n); const d = m.getChannelData(0); const step = Math.max(1, Math.floor(d.length / n));
  for (let i = 0; i < n; i++) { let mx = 0; for (let j = i * step; j < Math.min(d.length, (i + 1) * step); j += 8) mx = Math.max(mx, Math.abs(d[j])); out[i] = mx; }
  mixWaveform = out;
}
function drawTimeline() {
  const c = $('#timeline'), x = c.getContext('2d'), e = state.edit; if (!e) return;
  const W = c.width, H = c.height, D = e.duration; const X = (t) => t / D * W;
  x.clearRect(0, 0, W, H);
  e.clips.forEach((cl) => { x.fillStyle = cl.slow ? '#7e4bb8' : (cl.run % 2 ? '#2563eb' : '#3b82f6'); x.fillRect(X(cl.out0), 44, Math.max(1, X(cl.dur) - 1), 56); });
  if (mixWaveform) { x.fillStyle = 'rgba(255,255,255,0.55)'; for (let i = 0; i < mixWaveform.length; i++) { const h = mixWaveform[i] * 52; x.fillRect(i / mixWaveform.length * W, 72 - h / 2, Math.max(1, W / mixWaveform.length - 0.5), h); } }
  x.fillStyle = 'rgba(255,255,255,0.5)'; for (const b of e.beatsOut) if (b.t < D) x.fillRect(X(b.t), 102, 2, b.down ? 14 : 7);
  for (const z of e.zooms) { x.fillStyle = z.enabled ? '#ff3d6e' : '#553'; x.fillRect(X(z.t), 6, Math.max(3, X(z.attack + z.hold + z.release)), 14); }
  for (const tr of e.transitions) { x.fillStyle = tr.enabled ? '#f5b041' : '#554'; x.beginPath(); x.moveTo(X(tr.t), 24); x.lineTo(X(tr.t) - 9, 40); x.lineTo(X(tr.t) + 9, 40); x.fill(); }
  for (const s of e.sfx) { x.fillStyle = s.enabled ? '#2ecc71' : '#355'; x.beginPath(); x.arc(X(Math.max(0, s.t)), 130, 7, 0, 7); x.fill(); }
  for (const g of e.captions) { x.fillStyle = 'rgba(255,255,255,0.18)'; x.fillRect(X(g.s), 146, Math.max(2, X(g.e - g.s) - 2), 16); }
  for (const c of e.mg || []) { if (c.tpl === 'bars' || !c.enabled) continue; x.fillStyle = '#22d3ee'; x.fillRect(X(c.start), 26 + (c.track % 3) * 5, Math.max(3, X(c.dur)), 4); }
  if (player) { x.fillStyle = '#fff'; x.fillRect(X(player.t) - 2, 0, 4, H); }
}
function timelineSeek(ev) { const c = $('#timeline'); const r = c.getBoundingClientRect(); const t = clamp((ev.clientX - r.left) / r.width, 0, 1) * state.edit.duration; player.seek(t); }

/* ---------- panels ---------- */
function fillCutList() {
  const box = $('#cutList'); box.innerHTML = '';
  state.edit.segments.forEach((sg) => {
    const d = document.createElement('div'); d.className = 'item' + (sg.keep ? '' : ' off');
    d.innerHTML = `<div class="hd"><label class="chk" style="margin:0"><input type="checkbox" ${sg.keep ? 'checked' : ''}> ${fmtTimeMs(sg.s)} – ${fmtTimeMs(sg.e)}</label><span class="muted">${sg.keep ? 'kept' : 'removed'}: ${sg.reason}</span></div>`;
    d.querySelector('input').onchange = async (ev) => { sg.keep = ev.target.checked; rebuildFromCurrentSegments(); await refreshAll(true); };
    box.appendChild(d);
  });
}
function fillZoomList() {
  const box = $('#zoomList'); box.innerHTML = '';
  if (!state.edit.zooms.length) box.innerHTML = '<div class="muted">No zooms. Use “+ Add zoom at playhead”.</div>';
  state.edit.zooms.forEach((z, i) => {
    const d = document.createElement('div'); d.className = 'item' + (z.enabled ? '' : ' off');
    d.innerHTML = `<div class="hd"><label class="chk" style="margin:0"><input type="checkbox" class="en" ${z.enabled ? 'checked' : ''}> Zoom ${i + 1} @ ${fmtTimeMs(z.t)}</label>
      <span><button class="btn small pv">Preview</button> <button class="btn small del">✕</button></span></div>
      <div class="muted">${z.why || 'manual'}</div>
      <div class="kv"><label class="f">Strength <span class="av">${Math.round((z.amt - 1) * 100)}%</span><input type="range" class="amt" min="0" max="60" value="${Math.round((z.amt - 1) * 100)}"></label>
      <label class="f">Hold <span class="hv">${z.hold.toFixed(1)}s</span><input type="range" class="hold" min="0.1" max="4" step="0.1" value="${z.hold}"></label></div>
      <select class="ty"><option value="punch">Punch-in (fast)</option><option value="smooth">Smooth push-in</option></select>`;
    d.querySelector('.ty').value = z.type;
    d.querySelector('.en').onchange = (e) => { z.enabled = e.target.checked; d.classList.toggle('off', !z.enabled); refreshComposition(); redraw(); };
    d.querySelector('.amt').oninput = (e) => { z.amt = 1 + e.target.value / 100; d.querySelector('.av').textContent = e.target.value + '%'; redraw(); };
    d.querySelector('.hold').oninput = (e) => { z.hold = +e.target.value; d.querySelector('.hv').textContent = z.hold.toFixed(1) + 's'; redraw(); drawTimeline(); };
    d.querySelector('.hold').onchange = () => refreshComposition();
    d.querySelector('.ty').onchange = (e) => { z.type = e.target.value; z.attack = z.type === 'punch' ? 0.14 : 0.7; z.release = z.type === 'punch' ? 0.35 : 0.9; redraw(); drawTimeline(); };
    d.querySelector('.pv').onclick = () => player.playRange(Math.max(0, z.t - 0.6), z.t + z.attack + z.hold + z.release + 0.4);
    d.querySelector('.del').onclick = () => { state.edit.zooms.splice(i, 1); fillZoomList(); refreshComposition(); redraw(); };
    box.appendChild(d);
  });
}
function fillTransList() {
  const box = $('#transList'); box.innerHTML = '<div class="muted" style="margin-top:6px">Transitions at cuts:</div>';
  if (!state.edit.cuts.length) { box.innerHTML += '<div class="muted">No cuts in this edit.</div>'; return; }
  state.edit.cuts.forEach((c) => {
    const tr = state.edit.transitions.find((x) => Math.abs(x.t - c.t) < 1e-3);
    const d = document.createElement('div'); d.className = 'item';
    d.innerHTML = `<div class="hd"><span>Cut @ ${fmtTimeMs(c.t)} <span class="muted">${c.scene ? 'scene change' : 'jump cut'}</span></span><button class="btn small pv">Preview</button></div>
      <select><option value="none">Hard cut</option><option value="flash">Flash</option><option value="flashsoft">Soft warm flash</option><option value="whip">Whip pan</option>
      <option value="zoomblast">Zoom blast</option><option value="leak">Light leak</option><option value="glitch">Glitch</option><option value="crossfade">Crossfade</option><option value="dip">Dip to black</option><option value="wipe">Directional wipe</option></select>`;
    const sel = d.querySelector('select'); sel.value = tr && tr.enabled ? tr.type : 'none';
    sel.onchange = () => {
      const durT = TRANSITION_DUR;
      const ex = state.edit.transitions.find((x) => Math.abs(x.t - c.t) < 1e-3);
      if (sel.value === 'none') { if (ex) ex.enabled = false; }
      else if (ex) { ex.type = sel.value; ex.dur = durT[sel.value]; ex.enabled = true; }
      else state.edit.transitions.push({ id: 'trm' + c.t, t: c.t, type: sel.value, dur: durT[sel.value], dir: 1, enabled: true });
      redraw(); drawTimeline();
    };
    d.querySelector('.pv').onclick = () => player.playRange(Math.max(0, c.t - 1), c.t + 1);
    box.appendChild(d);
  });
}
function fillSfxList() {
  const box = $('#sfxList'); box.innerHTML = '<div class="muted" style="margin-top:6px">Sound effects (synthesised in the browser — royalty-free):</div>';
  state.edit.sfx.forEach((s) => {
    const d = document.createElement('div'); d.className = 'item' + (s.enabled ? '' : ' off');
    d.innerHTML = `<div class="hd"><label class="chk" style="margin:0"><input type="checkbox" ${s.enabled ? 'checked' : ''}> ${s.type} @ ${fmtTimeMs(Math.max(0, s.t))}</label><button class="btn small pv">Preview</button></div><div class="muted">${s.why}</div>`;
    d.querySelector('input').onchange = (e) => { s.enabled = e.target.checked; d.classList.toggle('off', !s.enabled); remixSoon(); drawTimeline(); };
    d.querySelector('.pv').onclick = () => player.playRange(Math.max(0, s.t - 0.5), s.t + 2.5);
    box.appendChild(d);
  });
  if (!state.edit.sfx.length) box.innerHTML += '<div class="muted">This style adds no sound effects.</div>';
}
function refreshComposition() { if (!state.edit) return; buildComposition(state.edit); fillMgList(); drawTimeline(); }
function fillMgList() {
  const box = $('#mgList'); if (!box || !state.edit) return; box.innerHTML = '';
  const mg = state.edit.mg || [];
  if (!mg.length) { box.innerHTML = '<div class="muted">No motion graphics for this edit. Titles need text (type a hook title or add subtitles); keyword animations need subtitles; callouts need a detected subject.</div>'; return; }
  for (const c of mg) {
    if (c.tpl === 'bars') continue;
    const d = document.createElement('div'); d.className = 'item' + (c.enabled ? '' : ' off');
    const extra = c.props.text ? ` “${escapeHtml(c.props.text)}”` : c.props.label ? ` “${escapeHtml(c.props.label)}”` : '';
    d.innerHTML = `<div class="hd"><label class="chk" style="margin:0"><input type="checkbox" ${c.enabled ? 'checked' : ''}> ${MG_NAMES[c.tpl] || c.tpl}${extra}</label><button class="btn small pv">Preview</button></div><div class="muted">${fmtTimeMs(c.start)} – ${fmtTimeMs(c.start + c.dur)}${c.props.fromSpeech ? ' · text taken from the first spoken sentence' : ''}</div>`;
    d.querySelector('input').onchange = (e) => { c.enabled = e.target.checked; d.classList.toggle('off', !c.enabled); redraw(); drawTimeline(); };
    d.querySelector('.pv').onclick = () => player.playRange(Math.max(0, c.start - 0.3), Math.min(state.edit.duration, c.start + Math.min(c.dur, 4) + 0.3));
    box.appendChild(d);
  }
}
function fillCapList() {
  const box = $('#capList'); box.innerHTML = ''; const caps = state.edit.captions;
  $('#subsEmpty').classList.toggle('hidden', !!caps.length);
  if (state.transcript) { const s = document.createElement('div'); s.className = 'muted'; s.textContent = `Source: ${state.transcript.source}. Edit text below (timing is kept).`; box.appendChild(s); }
  caps.forEach((g) => {
    const d = document.createElement('div'); d.className = 'item';
    d.innerHTML = `<div class="hd"><span class="muted">${fmtTimeMs(g.s)} – ${fmtTimeMs(g.e)}</span><span><button class="btn small pv">▶</button> <button class="btn small del">✕</button></span></div><input type="text">`;
    const inp = d.querySelector('input'); inp.value = g.text;
    inp.onchange = () => { editCaptionGroup(g, inp.value); };
    d.querySelector('.pv').onclick = () => player.playRange(Math.max(0, g.s - 0.2), g.e + 0.2);
    d.querySelector('.del').onclick = () => editCaptionGroup(g, '');
    box.appendChild(d);
  });
}
function editCaptionGroup(g, text) {
  const words = state.transcript.words; const idx = g.words.map((w) => w.wi); const a = Math.min(...idx), b = Math.max(...idx);
  const s = words[a].s, e = words[b].e; const repl = []; pushEstimatedWords(repl, text.trim(), s, e);
  words.splice(a, b - a + 1, ...repl.map((w) => ({ w: w.w, s: w.s, e: w.e })));
  state.edit.captions = buildCaptions(state.edit); refreshComposition(); fillCapList(); redraw(); drawTimeline();
}

/* ---------- export ---------- */
async function updateExportSupport() {
  const c = await exportCapabilities(); ui.caps = c;
  const lines = [];
  lines.push(c.webcodecs ? `✅ Frame-accurate export available: ${c.vcodec.toUpperCase()} video + ${c.acodec.toUpperCase()} audio → ${['vp9', 'av1'].includes(c.vcodec) && c.acodec === 'opus' ? 'WebM' : 'MP4'}` : `⚠️ Frame-accurate export unavailable (${c.why}).`);
  lines.push(c.recorder ? `✅ Real-time recording available: ${c.recorder.split(';')[0]}` : '⚠️ Real-time recording unavailable.');
  if (isIOS) lines.push('iPhone: keep Safari in the foreground with the screen on until export finishes. Then tap “Save / Share” → “Save Video” to put it in Photos.');
  $('#exportSupport').innerHTML = lines.join('<br>');
}
async function doExport() {
  if (!state.edit || exportAbort) return;
  if (player) player.pause();
  const W = +$('#exportRes').value, H = Math.round(W * 16 / 9), fps = +$('#exportFps').value;
  let method = $('#exportMethod').value; const caps = ui.caps || await exportCapabilities();
  if (method === 'auto') method = caps.webcodecs ? 'webcodecs' : 'realtime';
  exportAbort = new AbortController();
  $('#exportProgressWrap').classList.remove('hidden'); $('#exportResult').classList.add('hidden'); $('#exportBtn').disabled = true;
  const onProgress = (p, msg) => { $('#exportBar').style.width = `${Math.round(p * 100)}%`; if (msg) $('#exportStatus').textContent = msg; };
  await keepAwake(true);
  if (method === 'realtime') getAudioCtx().resume();
  await document.fonts.ready;
  if (!state.mix) await remixAudio();
  let result = null;
  try {
    if (method === 'webcodecs') {
      try { result = await exportWebCodecs({ W, H, fps, onProgress, signal: exportAbort.signal }); }
      catch (e) {
        if (e && e.name === 'AbortError') throw e;
        console.error(e); onProgress(0, `Frame-accurate export failed (${errText(e)}). Falling back to real-time recording…`); await sleep(1200);
        result = await exportRealtime({ W, H, fps, onProgress, signal: exportAbort.signal, vids });
      }
    } else result = await exportRealtime({ W, H, fps, onProgress, signal: exportAbort.signal, vids });
    showExportResult(result);
  } catch (e) {
    console.error(e); $('#exportStatus').innerHTML = `<span style="color:var(--err)">${e && e.name === 'AbortError' ? 'Export cancelled.' : 'Export failed: ' + escapeHtml(errText(e))}</span>`;
  } finally { exportAbort = null; $('#exportBtn').disabled = false; keepAwake(false); if (player) { player.curRun = -1; player.redraw(); } }
}
function showExportResult(r) {
  const url = URL.createObjectURL(r.blob); const name = `reel-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-')}.${r.ext}`;
  const v = $('#resultVideo'); if (v.src) URL.revokeObjectURL(v.src); v.src = url;
  const a = $('#downloadLink'); a.href = url; a.download = name;
  $('#resultInfo').textContent = `${(r.blob.size / 1e6).toFixed(1)} MB · ${r.info}. Play it above to check sound and timing.`;
  $('#exportStatus').textContent = 'Export finished ✔'; $('#exportBar').style.width = '100%';
  $('#exportResult').classList.remove('hidden');
  ui.lastExport = { blob: r.blob, name };
  window.__lastExport = ui.lastExport; // used by automated tests
}
async function shareExport() {
  const ex = ui.lastExport; if (!ex) return;
  const file = new File([ex.blob], ex.name, { type: ex.blob.type });
  if (navigator.canShare && navigator.canShare({ files: [file] })) { try { await navigator.share({ files: [file], title: 'Reel' }); return; } catch (e) { if (e && e.name === 'AbortError') return; } }
  $('#downloadLink').click();
}

function applyPreviewSize() { const hq = $('#hqPreview').checked; previewRenderer.resize(hq ? 1080 : 540, hq ? 1920 : 960); if (player) player.redraw(); }

function buildStatusTable() {
  const rows = [
    ['ok', 'Original audio in preview and export', 'Decoded from the file and re-mixed sample-accurately with every cut (no reliance on the video element’s sound).'],
    ['ok', 'Pause / silence / dead-time removal', 'Adaptive loudness analysis with padding so words are not clipped. Intensity changes how long pauses may be.'],
    ['ok', 'Scene, motion and subject detection', 'Frame differencing + colour histograms + skin-tone/motion centroid heuristics. Not face recognition.'],
    ['ok', 'Zooms, jump-cut reframing, Ken Burns', 'Placed on stressed syllables, keywords, motion peaks and music downbeats; every zoom editable with preview.'],
    ['ok', 'Effects (WebGL)', 'Colour grade, glow/bloom, sharpen, vignette, grain, flash, light leaks, whip pans, zoom blasts, glitch, motion blur, camera shake.'],
    ['ok', 'Speed ramps / slow motion', 'Only on high-motion moments without speech; audio follows the same speed curve.'],
    ['ok', 'Music + beat sync + ducking', 'Your file only. Tempo/beat tracking by onset autocorrelation; cuts, zooms and pulses snap to beats; music dips under speech.'],
    ['ok', 'Sound effects', 'Whoosh, impact, riser, bass hit — synthesised in the browser (no copyrighted samples).'],
    ['ok', 'Animated subtitles (5 styles) and titles', 'Rendered into the video frames; fully editable.'],
    ['ok', 'Motion graphics composition', 'Per-preset templates drawn into every exported frame: animated title cards (stacked, cinematic, sports, product, clean, minimal), kinetic keywords, subject callouts (ring + arrow, tracking reticle, labelled pointer), slow-motion tag, beat-frame pulses, cinema bars, lower third, call to action. Text only comes from your hook text or real subtitles; callouts only appear where a subject was detected.'],
    ['ok', 'Directional wipe transition', 'Two-layer GPU wipe with a glowing edge, between real shots of your video.'],
    ['ext', 'HyperFrames', 'Used as the design model (timed, seekable composition clips). Its MP4 renderer needs Node.js + headless Chrome + FFmpeg on a server, which GitHub Pages and iPhone Safari cannot run — so the same model is rendered natively in the browser instead.'],
    ['exp', 'On-device speech recognition', 'Real ML model (OpenAI Whisper via transformers.js). Downloads 40–80 MB on first use; slow on long videos; needs a modern browser. Words in silence are discarded to avoid invented text.'],
    ['ext', 'OpenAI Whisper API', 'External service; needs your API key; your audio is sent to OpenAI.'],
    ['exp', 'Filler-word & restart removal', 'Uses the transcript. Whisper often omits “um/uh”, so results vary.'],
    ['exp', 'Target length trimming', 'Drops the least energetic phrases/moments; check the result.'],
    ['exp', 'Content-type detection', 'Rule-based (speech modulation, motion, scene rate) — a suggestion, not AI.'],
    ['ok', 'Frame-accurate MP4 export', 'WebCodecs H.264 + AAC (Chrome/Edge, Android, Safari with WebCodecs audio encoding). Falls back automatically.'],
    ['ok', 'Real-time export fallback', 'MediaRecorder (MP4 on Safari, WebM on Firefox). Runs at playback speed; keep the screen on.'],
  ];
  $('#statusTable').innerHTML = rows.map(([k, a, b]) => `<tr><td><span class="badge ${k}">${k === 'ok' ? 'working' : k === 'exp' ? 'experimental' : 'external'}</span></td><td><b>${a}</b><br><span class="muted">${b}</span></td></tr>`).join('');
}

/* ---------- wiring ---------- */
function escapeHtml(t) { return String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }
window.addEventListener('error', (ev) => { const m = errText(ev.error || ev.message); console.error('Uncaught', ev.error || ev.message); try { log('Unexpected error: ' + m, 'err'); } catch (x) { } });
window.addEventListener('unhandledrejection', (ev) => { console.error('Unhandled rejection', ev.reason); try { log('Unexpected error: ' + errText(ev.reason), 'err'); } catch (x) { } });
function wire() {
  buildStyleGrid(); buildStatusTable();
  $('#gradePreset').innerHTML = Object.entries(GRADES).map(([k, g]) => `<option value="${k}">${g.label}</option>`).join('');
  const saved = loadSavedSettings();
  applyStyleDefaults(STYLES[saved.style] ? saved.style : 'viral');
  for (const k of PERSIST_KEYS) if (saved[k] !== undefined && k !== 'style') state.settings[k] = saved[k];
  buildStyleGrid(); syncControlsFromSettings();
  const rerun = async () => { saveSettings(); if (state.edit) { runAutoEdit(); await refreshAll(true); } };
  const rebuildOnly = async () => { saveSettings(); if (state.edit) { rebuildFromCurrentSegments(); await refreshAll(true); } };
  $('#beatsPerCut').onchange = (e) => { state.settings.beatsPerCut = e.target.value; rebuildOnly(); };
  $('#contentMode').onchange = (e) => { state.settings.contentMode = e.target.value; rebuildOnly(); };
  $('#silAuto').onchange = (e) => { state.settings.silAuto = e.target.checked; $('#silDb').disabled = e.target.checked; updateLabels(); rerun(); };
  $('#silDb').oninput = (e) => { state.settings.silDb = +e.target.value; updateLabels(); }; $('#silDb').onchange = rerun;
  $('#minPause').oninput = (e) => { state.settings.minPause = +e.target.value; updateLabels(); }; $('#minPause').onchange = rerun;
  $('#drift').onchange = (e) => { state.settings.drift = e.target.value; rebuildOnly(); };
  $('#driftAmt').oninput = (e) => { state.settings.driftAmt = +e.target.value; updateLabels(); }; $('#driftAmt').onchange = rebuildOnly;
  $('#pulseZoom').oninput = (e) => { state.settings.pulseZoom = +e.target.value; updateLabels(); redraw(); };
  $('#letterbox').onchange = (e) => { state.settings.letterbox = e.target.checked; saveSettings(); redraw(); };
  $('#transType').onchange = (e) => { state.settings.transType = e.target.value; rebuildOnly(); };
  $('#transFreq').oninput = (e) => { state.settings.transFreq = +e.target.value; updateLabels(); }; $('#transFreq').onchange = rebuildOnly;
  try { const k = localStorage.getItem('reels_openai_key'); if (k) { $('#openaiKey').value = k; $('#rememberKey').checked = true; } } catch (e) { }
  $('#videoInput').onchange = (e) => { const f = e.target.files[0]; if (f) loadVideo(f); };
  $('#musicInput').onchange = (e) => { const f = e.target.files[0]; if (f) loadMusic(f); };
  $('#musicRemove').onclick = async () => { state.music = null; $('#musicInput').value = ''; $('#musicInfo').textContent = 'No music — the original audio is used.'; $('#musicRemove').classList.add('hidden'); if (state.edit) { rebuildFromCurrentSegments(); await refreshAll(true); } };
  $('#intensitySeg').onclick = async (e) => { const b = e.target.closest('button'); if (!b) return; $$('#intensitySeg button').forEach((x) => x.classList.toggle('on', x === b)); state.settings.intensity = b.dataset.v; saveSettings(); if (state.edit) { runAutoEdit(); await refreshAll(true); } };
  $('#targetLen').onchange = async (e) => { state.settings.targetLen = +e.target.value; saveSettings(); if (state.edit) { runAutoEdit(); await refreshAll(true); } };
  $('#framing').onchange = (e) => { state.settings.framing = e.target.value; redraw(); };
  $('#removeFillers').onchange = async (e) => { state.settings.removeFillers = e.target.checked; if (state.edit) { runAutoEdit(); await refreshAll(true); } };
  $('#asrMode').onchange = (e) => { const m = e.target.value; $('#asrLocalOpts').classList.toggle('hidden', m !== 'local'); $('#asrOpenaiOpts').classList.toggle('hidden', m !== 'openai'); $('#asrSrtOpts').classList.toggle('hidden', m !== 'srt'); };
  $('#srtInput').onchange = async (e) => { const f = e.target.files[0]; if (!f) return; state.pendingSrt = parseSrt(await f.text()); state.pendingSrtName = f.name; $('#srtInfo').textContent = `${f.name}: ${state.pendingSrt.length} words`; };
  $('#autoEditBtn').onclick = doAutoEdit;
  $('#playBtn').onclick = () => { if (!player) return; if (player.playing) { player.pause(); $('#playBtn').textContent = '▶ Play'; } else { getAudioCtx().resume(); player.play(); $('#playBtn').textContent = '❚❚ Pause'; } };
  const scrub = $('#scrub');
  scrub.oninput = () => { ui.scrubbing = true; if (player && state.edit) { const t = scrub.value / 1000 * state.edit.duration; $('#timeLabel').textContent = `${fmtTime(t)} / ${fmtTime(state.edit.duration)}`; ui.scrubT = t; if (!ui.seekPending) { ui.seekPending = true; player.seek(t).finally(() => { ui.seekPending = false; if (Math.abs(ui.scrubT - player.t) > 0.05) player.seek(ui.scrubT); }); } } };
  scrub.onchange = () => { ui.scrubbing = false; $('#playBtn').textContent = '▶ Play'; };
  const tl = $('#timeline'); let drag = false;
  tl.onpointerdown = (e) => { if (!state.edit) return; drag = true; tl.setPointerCapture(e.pointerId); timelineSeek(e); };
  tl.onpointermove = (e) => { if (drag) timelineSeek(e); }; tl.onpointerup = () => (drag = false);
  $('#hqPreview').onchange = applyPreviewSize;
  $('#compareOriginal').onchange = (e) => { if (player) { player.bypass = e.target.checked; player.redraw(); } };
  $('#tabs').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; $$('#tabs button').forEach((x) => x.classList.toggle('on', x === b)); $$('.tabpane').forEach((p) => p.classList.toggle('on', p.dataset.pane === b.dataset.tab)); };
  $('#rerunBtn').onclick = async () => { runAutoEdit(); await refreshAll(true); };
  $('#zoomGlobal').oninput = (e) => { state.settings.zoomGlobal = e.target.value / 100; updateLabels(); redraw(); };
  $('#jumpZoom').onchange = (e) => { state.settings.jumpZoom = e.target.checked; redraw(); };
  $('#addZoomBtn').onclick = () => {
    if (!state.edit) return; const t = player.t; const { srcT } = player.sourceFor(t); const ip = interestAt(srcT); const st = STYLES[state.settings.style];
    state.edit.zooms.push({ id: 'zm' + Date.now(), t, attack: 0.14, hold: 0.8, release: 0.35, amt: Math.max(1.15, st.zoomAmt), type: 'punch', ax: ip.x, ay: ip.y, enabled: true, why: 'added manually', v: 1 });
    state.edit.zooms.sort((a, b) => a.t - b.t); fillZoomList(); refreshComposition(); redraw();
  };
  const fxMap = { fxTransitions: 'transitions', fxShake: 'shake', fxMotionBlur: 'motionBlur', fxBeatPulse: 'beatPulse', fxGraphics: 'graphics', fxProgress: 'progress' };
  for (const [id, key] of Object.entries(fxMap)) $('#' + id).onchange = (e) => { state.settings.fx[key] = e.target.checked; redraw(); };
  $('#fxRamps').onchange = async (e) => { state.settings.fx.ramps = e.target.checked; if (state.edit) { rebuildFromCurrentSegments(); await refreshAll(true); } };
  $('#gradePreset').onchange = (e) => { state.settings.grade = e.target.value; state.settings.look = { ...GRADES[e.target.value] }; buildLookSliders(); redraw(); };
  $('#lookReset').onclick = () => { const g = STYLES[state.settings.style].grade; state.settings.grade = g; state.settings.look = { ...GRADES[g] }; $('#gradePreset').value = g; buildLookSliders(); redraw(); };
  const vol = (id, key, div = 100) => { $('#' + id).oninput = (e) => { state.settings[key] = e.target.value / div; updateLabels(); saveSettings(); remixSoon(); }; };
  vol('volOrig', 'volOrig'); vol('volMusic', 'volMusic'); vol('volSfx', 'volSfx'); vol('duckAmt', 'duckAmt');
  $('#duck').onchange = (e) => { state.settings.duck = e.target.checked; remixSoon(); };
  $('#normalize').onchange = (e) => { state.settings.normalize = e.target.checked; remixSoon(); };
  $('#musicOffset').oninput = (e) => { state.settings.musicOffset = +e.target.value; updateLabels(); };
  $('#musicOffset').onchange = async () => { if (state.edit) { rebuildFromCurrentSegments(); await refreshAll(true); } };
  $('#transcribeNowBtn').onclick = async () => {
    if (!state.analysis) { alert('Run AUTO EDIT first.'); return; }
    if ($('#asrMode').value === 'none') { alert('Choose a speech recognition option in step 4 first.'); $('#asrMode').scrollIntoView({ behavior: 'smooth' }); return; }
    $('#progressCard').classList.remove('hidden'); ui.busy = true; await keepAwake(true);
    try { await runTranscription(true); runAutoEdit(); await refreshAll(true); setProgress(1, 'Subtitles updated'); } finally { ui.busy = false; keepAwake(false); }
  };
  $('#subsOn').onchange = (e) => { state.settings.subsOn = e.target.checked; redraw(); };
  $('#capStyle').onchange = (e) => { const s = e.target.value; state.settings.cap = { style: s, ...CAPTION_DEFAULTS[s], keywords: state.settings.cap.keywords }; syncControlsFromSettings(); if (state.edit) { state.edit.captions = buildCaptions(state.edit); fillCapList(); } redraw(); };
  const cap = (id, key, conv = (v) => v, rebuild = false) => { $('#' + id).oninput = $('#' + id).onchange = (e) => { state.settings.cap[key] = conv(e.target.type === 'checkbox' ? e.target.checked : e.target.value); updateLabels(); if (rebuild && state.edit) { state.edit.captions = buildCaptions(state.edit); refreshComposition(); fillCapList(); } redraw(); }; };
  cap('capFont', 'font'); cap('capSize', 'size', Number); cap('capPos', 'pos', Number); cap('capColor', 'color'); cap('capHl', 'hl'); cap('capStroke', 'stroke');
  cap('capUpper', 'upper'); cap('capKeywords', 'keywords'); cap('capWords', 'words', Number, true);
  $('#hookText').oninput = (e) => { state.settings.hookText = e.target.value.trim(); refreshComposition(); redraw(); };
  $('#lowerThird').oninput = (e) => { state.settings.lowerThird = e.target.value.trim(); refreshComposition(); redraw(); };
  $('#ctaText').oninput = (e) => { state.settings.ctaText = e.target.value.trim(); refreshComposition(); redraw(); };
  $('#autoTitle').checked = state.settings.autoTitle;
  $('#autoTitle').onchange = (e) => { state.settings.autoTitle = e.target.checked; saveSettings(); refreshComposition(); redraw(); };
  $('#hookFromSpeech').onclick = () => {
    const w = state.transcript && state.transcript.words; if (!w || !w.length) { alert('No transcript yet — add subtitles first.'); return; }
    const out = []; for (const x of w) { out.push(x.w.trim()); if (out.length >= 7 || /[.?!]$/.test(x.w.trim())) break; }
    $('#hookText').value = out.join(' ').replace(/[.,]$/, ''); state.settings.hookText = $('#hookText').value; refreshComposition(); redraw();
  };
  $('#exportBtn').onclick = doExport;
  $('#exportCancel').onclick = () => exportAbort && exportAbort.abort();
  $('#shareBtn').onclick = shareExport;
  document.fonts && document.fonts.load('900 40px Montserrat').then(() => redraw()).catch(() => { });
  loadMediabunny();
}
wire();
window.__reels = { state, probeMedia, decodeAudioFromFile, computeView, interestAt, refreshComposition, runAutoEdit, renderMix, exportWebCodecs, exportRealtime, exportCapabilities, get player() { return player; } };
