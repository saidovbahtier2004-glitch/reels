"""Single source of truth: word timings, scene starts, cue points and SFX events.
Visuals (scene.html) and audio (audio.py) both read timeline.json, so they stay in sync.
Timings are *estimated* from text length (no voice recording was supplied)."""
import json, re

def spoken_len(s):
    s = re.sub(r"[^\w‘’'+]", "", s)
    return max(len(s), 2)

# (display, spoken-override, pause_before)
def W(d, sp=None, pause=0.0): return (d, sp, pause)

SCENES = [
 dict(id="hook", sub=False, tail=0.30, words=[W("Do‘stlar,"),W("bu"),W("videoni"),W("AI"),W("montaj"),W("qildi"),W("desam,"),W("ishonasizmi?",None,0.28)],
      cues=dict(dostlar=0,ai=3,montaj=4,ishon=7)),
 dict(id="intro", sub=True, tail=0.35, words=[W("Men"),W("Saidov"),W("Baxtiyor,"),W("mobilograf"),W("sohasida"),W("2","ikki"),W("yildan"),W("buyon"),W("ishlab"),W("kelmoqdaman"),W("va"),W("hozirda"),W("10","o‘nta"),W("dan"),W("ortiq"),W("loyihalar"),W("bilan"),W("ishlab"),W("kelmoqdaman.")],
      cues=dict(name=1,mob=3,two=5,work=8,ten=12,proj=15)),
 dict(id="ai", sub=True, tail=0.35, words=[W("Siz"),W("ko‘rib"),W("turganingizdek,"),W("mana"),W("shu"),W("videoni"),W("Claude"),W("AI"),W("yasab"),W("bermoqda-da,"),W("do‘stlar.")],
      cues=dict(see=1,video=5,claude=6,ai=7,friends=10)),
 dict(id="grow", sub=True, tail=0.30, words=[W("Hozirda"),W("AI"),W("juda"),W("ham"),W("kundan"),W("kunga"),W("rivojlanib"),W("ketmoqda.")],
      cues=dict(ai=1,kundan=4,riv=6)),
 dict(id="want", sub=False, tail=0.30, words=[W("Siz"),W("ham"),W("xuddi"),W("shunday"),W("motion"),W("videolar"),W("yasamoqchimisiz?")],
      cues=dict(motion=4,yas=6)),
 dict(id="tg", sub=True, tail=0.35, words=[W("Albatta,"),W("sizlar"),W("uchun"),W("Telegramda"),W("yopiq"),W("kanalda"),W("video"),W("darslik"),W("joylab"),W("qo‘yganman.")],
      cues=dict(tg=3,closed=4,video=6,lesson=7)),
 dict(id="plus", sub=False, tail=0.45, words=[W("Bu"),W("darslikni"),W("olish"),W("uchun"),W("kommentariyada"),W("‘+’","plyus"),W("belgisini"),W("yozib"),W("qoldiring,"),W("men"),W("sizga"),W("silkasini"),W("jo‘nataman.")],
      cues=dict(open=2,comment=4,plus=5,send=8,me=9)),
 dict(id="link", sub=True, tail=0.35, words=[W("Men"),W("sizga"),W("silkasini"),W("jo‘nataman,"),W("siz"),W("ham"),W("xuddi"),W("shunday"),W("motion"),W("videolarni"),W("osongina"),W("yasashni"),W("o‘rganasiz.")],
      cues=dict(me=0,link=2,tg=4,motion=8,easy=10,learn=11)),
 dict(id="cta", sub=False, tail=0.9, words=[W("Obuna"),W("bo‘lib"),W("qo‘yishni"),W("unutmang,"),W("kommentga"),W("plus"),W("belgisini"),W("qoldiring,"),W("ko‘rishguncha!")],
      cues=dict(sub=0,plus=5,bye=8)),
]
LEAD = 0.12

def build():
    t = 0.0; out = []
    for s in SCENES:
        c = LEAD; ws = []
        for d, sp, pause in s["words"]:
            c += pause
            n = spoken_len(sp or d)
            dur = 0.046*n + 0.045
            ws.append(dict(w=d, t0=round(t+c,3), t1=round(t+c+dur,3)))
            c += dur + (0.16 if d.endswith((",",".")) else 0.01)
        dur_scene = round(c + s["tail"], 3)
        cues = {k: ws[i]["t0"] for k, i in s["cues"].items()}
        out.append(dict(id=s["id"], sub=s["sub"], start=round(t,3), dur=dur_scene, words=ws, cues=cues))
        t += dur_scene
    return dict(total=round(t,3), fps=30, scenes=out)

if __name__ == "__main__":
    tl = build()
    json.dump(tl, open("timeline.json","w"), ensure_ascii=False, indent=1)
    for s in tl["scenes"]: print(f'{s["id"]:6} {s["start"]:6.2f} +{s["dur"]:.2f}')
    print("total", tl["total"])
