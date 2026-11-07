# Masha va katta muzqaymoq — reel ssenariysi

Asos: `gemini_generated_video` (20 s, 9:16, 720x1280, 24 fps).
Vazifa: shu yo'nalishda yangi video, timsoh o'rniga **Masha**.

## Asl videoning tahlili

| Vaqt | Nima bo'ladi |
|------|--------------|
| 0–3 s | Sariq kepkali kichkina yashil timsoh quyoshli bog'da ulkan, 5 qavatli rang-barang muzqaymoqni (tepasida olcha) quchoqlab turibdi, kulib qo'yadi |
| 3–5 s | Sakraydi, muzqaymoq qo'lidan uchib ketadi, o'zi o'tloqqa yiqiladi |
| 5–7 s | Pushti shar havodan tushib, boshiga "shalop" etib tushadi — pushti sachrash |
| 7–10 s | Yuzi pushti muzqaymoqqa belangan, boshida vafli konus "qalpoq" bo'lib qolgan; yaqin plan, til chiqarib kuladi, "zo'r" ishorasi |
| 10–15 s | Yoniga binafsha ko'ylakli qizcha keladi, qo'lida kichkina muzqaymoq — uni timsohga beradi |
| 15–20 s | Qizcha ro'molcha bilan yuzini artadi, ikkalasi baxtli kulishadi |

Uslub: 3D, Pixar/Disney uslubidagi yumshoq animatsiya, katta yaltiroq ko'zlar, pastel ranglar,
yorqin kunduzgi quyosh, orqada daraxtlar va gullar, sayoz fokus (bokeh). Kamera: o'rta plan → yaqin plan → ikki kishilik o'rta plan.
Hikoya: kulgili omadsizlik → do'stlik/mehribonlik bilan yakun.

## Personajlar (original dizayn)

**Masha** — 5 yoshli qizcha: kalta jigarrang soch (bob), sochida sariq romashka shaklidagi to'g'nog'ich,
katta jigarrang ko'zlar, yonoqlarida sepkil, romashka naqshli yalpiz-yashil ko'ylakcha, oq krossovka.
(Mavjud multfilm personajlaridan nusxa emas — o'zimizning original Masha.)

**Do'sti** — muzqaymoq aravachasida ishlaydigan kichkina kulrang mushukcha, ko'k fartuk kiygan.
(Asl videodagi malika qizcha taniqli multfilm qahramoniga juda o'xshaydi, shuning uchun uni ham original personajga almashtirdik.)

## Promptlar (2 ta klip × 10 s, 9:16)

**Klip 1 (0–10 s):**
```
3D Pixar-style animated short, vertical 9:16, sunny park with lush trees, colorful flowers and soft bokeh.
An original character: Masha, a cheerful 5-year-old girl with a short chestnut-brown bob, a yellow daisy hair clip,
big brown eyes, freckles, a mint-green dress with a daisy print and white sneakers.
She proudly hugs a giant five-scoop pastel ice cream cone (pink, mint, lavender, yellow, pink, rainbow sprinkles, a cherry on top), almost as tall as she is, and giggles.
She does a happy little hop — the scoops wobble and fly into the air, she lands on her bottom on the grass.
The pink top scoop falls and splats onto her head with a big pink splash; the waffle cone lands upside down on her head like a party hat.
Close-up: her face covered in pink ice cream, she blinks, licks her lips, laughs and gives a thumbs up.
Bright warm daylight, soft shadows, playful comedic timing, smooth animation.
```

**Klip 2 (10–20 s):**
```
Same 3D Pixar-style park scene, vertical 9:16. Masha (5-year-old girl, chestnut-brown bob, yellow daisy hair clip,
freckles, mint-green daisy dress) sits on the grass with pink ice cream on her face and a waffle cone on her head like a hat.
A small fluffy grey kitten in a little blue apron walks over from a striped ice cream cart, holding a small cone with one blue scoop,
and hands it to Masha. Masha's eyes sparkle as she takes it. The kitten gently wipes her face with a white napkin.
Medium two-shot, both laugh happily together, warm sunlight, soft bokeh flowers, heartwarming ending.
```

Tavsiya etilgan model: Higgsfield `seedance_2_5`, 9:16, 10 s. Bitta klip ≈ 70 kredit (jami ≈ 140).
Ikki klipni keyin `ffmpeg` bilan birlashtirish:
```
ffmpeg -i klip1.mp4 -i klip2.mp4 -filter_complex "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1" masha.mp4
```
