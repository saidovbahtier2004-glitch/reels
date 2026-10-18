import sys, json, base64, subprocess, os, asyncio, http.server, threading, functools
from playwright.async_api import async_playwright
HERE = os.path.dirname(os.path.abspath(__file__)); CHROME = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"
words = json.load(open(f"{HERE}/words.json"))["words"]; face = json.load(open(f"{HERE}/face.json")); TOTAL = face["n"] / 60
def serve(port):
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=HERE); h.log_message = lambda *a, **k: None
    s = http.server.ThreadingHTTPServer(("127.0.0.1", port), h); threading.Thread(target=s.serve_forever, daemon=True).start()
async def page(pw, port):
    b = await pw.chromium.launch(executable_path=CHROME, args=["--no-sandbox", "--disable-gpu"]); p = await b.new_page(viewport={"width": 540, "height": 960})
    p.on("pageerror", lambda e: print("PAGEERR", e)); p.on("console", lambda m: print("CONSOLE", m.text) if m.type == "error" else None)
    await p.goto(f"http://127.0.0.1:{port}/edit.html?sc=1")
    await p.evaluate("document.fonts.load('900 80px Inter').then(()=>document.fonts.load('80px \"Noto Color Emoji\"'))")
    await p.evaluate("([w,f,t])=>initEdit(w,f,t)", [words, face, TOTAL]); return b, p
async def grab(p, T, q=.95):
    d = await p.evaluate(f"(async()=>{{await renderEdit({T});return document.getElementById('c').toDataURL('image/jpeg',{q})}})()"); return base64.b64decode(d.split(",", 1)[1])
async def stills(times, out, port):
    os.makedirs(out, exist_ok=True)
    async with async_playwright() as pw:
        b, p = await page(pw, port)
        for T in times: open(f"{out}/f_{T:06.2f}.jpg", "wb").write(await grab(p, T))
        await b.close()
async def worker(f0, f1, out, port):
    async with async_playwright() as pw:
        b, p = await page(pw, port)
        ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", "60", "-c:v", "mjpeg", "-i", "-", "-c:v", "libx264", "-preset", "fast", "-crf", "15", "-pix_fmt", "yuv420p", "-r", "60", out], stdin=subprocess.PIPE)
        for f in range(f0, f1):
            ff.stdin.write(await grab(p, f / 60))
            if f % 120 == 0: print(out, f, "/", f1, flush=True)
        ff.stdin.close(); ff.wait(); await b.close()
if __name__ == "__main__":
    port = 8765 + os.getpid() % 100; serve(port)
    if sys.argv[1] == "stills": asyncio.run(stills([float(x) for x in sys.argv[3:]], sys.argv[2], port))
    else:
        n = int(sys.argv[2]); out = sys.argv[3]; os.makedirs(out, exist_ok=True); tot = face["n"]; per = -(-tot // n)
        async def run(): await asyncio.gather(*[worker(i * per, min(tot, (i + 1) * per), f"{out}/seg{i}.mp4", port) for i in range(n)])
        asyncio.run(run())
