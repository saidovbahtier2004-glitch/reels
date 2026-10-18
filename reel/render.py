import sys, json, base64, subprocess, os, asyncio
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); TL = json.load(open(f"{HERE}/timeline.json"))
CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

async def page_for(pw, sc):
    b = await pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox", "--disable-gpu"])
    p = await b.new_page(viewport={"width": 540, "height": 960})
    p.on("pageerror", lambda e: print("PAGEERR", e)); p.on("console", lambda m: print("CONSOLE", m.text) if m.type == "error" else None)
    await p.add_init_script(f"window.TL={json.dumps(TL, ensure_ascii=False)};")
    await p.goto(f"file://{HERE}/scene.html?sc={sc}")
    await p.evaluate("document.fonts.load('900 80px Inter').then(()=>document.fonts.load('italic 400 80px \"DejaVu Serif\"')).then(()=>document.fonts.load('80px \"Noto Color Emoji\"'))")
    await p.evaluate("initCanvases()")
    return b, p

async def grab(p, T, q=.93):
    d = await p.evaluate(f"(()=>{{renderFrame({T});return document.getElementById('c').toDataURL('image/jpeg',{q})}})()")
    return base64.b64decode(d.split(",", 1)[1])

async def stills(times, sc, outdir):
    os.makedirs(outdir, exist_ok=True)
    async with async_playwright() as pw:
        b, p = await page_for(pw, sc)
        for T in times:
            open(f"{outdir}/f_{T:06.2f}.jpg", "wb").write(await grab(p, T))
        await b.close()

async def worker(f0, f1, sc, fps, out, q):
    async with async_playwright() as pw:
        b, p = await page_for(pw, sc)
        ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
            "-c:v", "libx264", "-preset", "fast", "-crf", "14", "-pix_fmt", "yuv420p", "-r", str(fps), out], stdin=subprocess.PIPE)
        for f in range(f0, f1):
            ff.stdin.write(await grab(p, f / fps, q))
            if f % 30 == 0: print(f"{out} frame {f}/{f1}", flush=True)
        ff.stdin.close(); ff.wait(); await b.close()

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "stills":
        sc = float(sys.argv[2]); out = sys.argv[3]; times = [float(x) for x in sys.argv[4:]]
        asyncio.run(stills(times, sc, out))
    else:  # video sc nworkers outdir [start end]
        sc = float(sys.argv[2]); n = int(sys.argv[3]); outdir = sys.argv[4]; os.makedirs(outdir, exist_ok=True)
        fps = TL["fps"]; total = int(round(TL["total"] * fps)); per = -(-total // n)
        async def run():
            await asyncio.gather(*[worker(i * per, min(total, (i + 1) * per), sc, fps, f"{outdir}/seg{i}.mp4", .95) for i in range(n)])
        asyncio.run(run())
