# 🎵 Musiqa topuvchi Telegram bot

Foydalanuvchi yuboradi:

| Nima | Bot nima qiladi |
|---|---|
| Qo'shiq nomi / ijrochi | Ro'yxat chiqaradi (8 tadan, ⬅️ ➡️ sahifalar), tanlanganini audio qilib yuboradi |
| Video, reels, dumaloq video, GIF | Ichidagi qo'shiqni Shazam orqali aniqlaydi va yuboradi |
| Ovozli xabar | Atrofda chalinayotgan qo'shiqni aniqlaydi |
| Audio fayl | Nomini aniqlab beradi |

Video/audiodan 0, 15, 35 va 60-soniyalardagi parchalar sinab ko'riladi, shuning uchun musiqa o'rtada boshlansa ham topiladi.

Audio sifatida Deezer'ning rasmiy **30 soniyalik preview**'i yuboriladi. To'liq qo'shiqni tinglash uchun Spotify / YouTube / Apple Music / Deezer / Shazam tugmalari bor.

## Ishga tushirish

1. Telegramda **@BotFather** → `/newbot` → token oling.
2. Kompyuterda **Python 3.10+** va **ffmpeg** o'rnatilgan bo'lsin
   (Windows: `winget install ffmpeg`, Ubuntu: `sudo apt install ffmpeg`, macOS: `brew install ffmpeg`).
3. Kutubxonalarni o'rnating:
   ```bash
   cd music_bot
   pip install -r requirements.txt
   ```
4. `.env.example` faylidan nusxa olib `.env` deb nomlang va tokenni yozing:
   ```
   BOT_TOKEN=123456789:AAAA...
   ```
5. Botni yoqing:
   ```bash
   python bot.py
   ```

Bot kompyuter yoqiq turganda ishlaydi. Doimiy ishlashi uchun uni VPS'ga (yoki Railway, Render kabi xostingga) qo'ying. U yerda ham xuddi shu buyruq ishlatiladi.

## Cheklovlar

- Telegram botlar 20 MB dan katta faylni yuklab ololmaydi, shuning uchun uzun videolarni qisqartirib yuboring.
- Instagram/TikTok havolasi qabul qilinmaydi, videoning o'zini yuborish kerak.

## O'z kutubxonangiz (to'liq qo'shiqlar)

Tarqatishga **ruxsatingiz bor** qo'shiqlarni bot to'liq yuborishi mumkin:

1. Telegramda yangi **maxfiy kanal** oching.
2. Botni kanalga **admin** qilib qo'shing (xabar yozish, tahrirlash va pin qilish huquqlari bilan).
3. Kanalga `/id` deb yozing. Bot kanal ID'sini yuboradi (masalan `-1001234567890`).
4. Render → **Environment** → `LIBRARY_CHANNEL_ID` = shu ID → **Save**.
5. Kanalga MP3 fayllarni tashlang. Bot ularni avtomatik eslab qoladi.

Qidiruvda kutubxonadagi qo'shiqlar 🎧 belgisi bilan birinchi chiqadi va to'liq yuboriladi.

Kanaldagi buyruqlar:
- `/count`: kutubxonada nechta qo'shiq borligini ko'rsatadi
- `/del`: audioga **javob (reply)** qilib yozilsa, o'sha qo'shiqni kutubxonadan o'chiradi

Bot kanalda `library.json` faylini pin qilib qo'yadi, u qo'shiqlar ro'yxati. Uni o'chirmang.

## Admin panel

1. Botga `/myid` deb yozing, bot sizning ID raqamingizni yuboradi.
2. Render → **Environment** → `ADMIN_IDS` = shu raqam. Bir nechta admin bo'lsa, vergul bilan yozing: `111,222`.
3. Botga `/admin` yozing.

| Buyruq | Nima qiladi |
|---|---|
| `/admin` | Panel: statistika va tugmalar |
| `/stats` | Jami musiqalar, bugun qo'shilganlar, ijrochilar, hajm, davomiylik |
| `/today` | Bugun qo'shilgan musiqalar ro'yxati |
| `/find so'z` | Bazadan qidirish (ID'lari bilan) |
| `/dups` | Bir xil nomli (takroriy) musiqalar |
| `/check` | Bazani tekshirish: buzilgan file_id, yo'q maydonlar |
| `/delete ID` | Musiqani bazadan o'chirish |

Baza har bir musiqa uchun quyidagilarni saqlaydi: ID, nom, ijrochi, `file_id`, `file_unique_id`, davomiylik,
fayl hajmi, qo'shilgan sana, manba kanal. `file_unique_id` bir xil bo'lgan fayl qayta qo'shilmaydi.
Foydalanuvchiga qo'shiq `file_id` orqali yuboriladi, serverga yuklab olinmaydi.

## Ommaviy import (faqat litsenziyali musiqa)

Import uchun `importer/` paketi ishlatiladi:

| Fayl | Vazifasi |
|---|---|
| `models.py` | `TrackMeta` (nom, ijrochi, ISRC, litsenziya...) va `AudioFile` |
| `csv_import.py` | CSV o'qish va tekshirish. `license_id` majburiy, muddati o'tgan yoki takroriy qatorlar rad etiladi |
| `providers.py` | `MusicProvider` interfeysi, `HttpDistributorProvider` shabloni va `PROVIDERS` ro'yxati |
| `runner.py` | `ImportManager`: batch, progress, pauza, davom ettirish, qayta urinish |
| `telegram_ui.py` | Admin buyruqlari |

**Usullar (admin, botga shaxsiy chatda):**
1. **CSV + fayllar.** CSV'ni hujjat qilib yuborasiz ([shablon](importer/template.csv)), keyin MP3'larni yuborasiz.
   Fayllar `file` ustuni, «Ijrochi - Nomi» yoki audio teglari bo'yicha moslanadi. CSV'da yo'q fayl qabul qilinmaydi.
   Kanalga `file_id` bilan yuboriladi, qayta yuklab olinmaydi.
2. **CSV + distributor.** CSV'ni `provider distributor` izohi bilan yuborasiz. Audio distributor API'sidan olinadi.
3. **Katalog sinxroni.** `/import_sync distributor` buyrug'i distributor katalogini sahifalab import qiladi.

Buyruqlar: `/import`, `/import_status [ID]`, `/import_pause ID`, `/import_resume ID`, `/import_cancel ID`,
`/import_finish ID`, `/import_failed ID`, `/import_retry ID`.

**Distributorni ulash** (Render → Environment):
```
PROVIDER_DISTRIBUTOR_BASE_URL=https://api.distributor.example/v1
PROVIDER_DISTRIBUTOR_API_KEY=...            # Bearer token
PROVIDER_DISTRIBUTOR_ALLOWED_HOSTS=cdn.distributor.example   # audio CDN bo'lsa
```
Distributor API hujjatlari kelgach, `HttpDistributorProvider` ichidagi endpoint va maydon nomlarini moslang.
Boshqa API bo'lsa, `MusicProvider`'dan yangi klass yozib, uni `PROVIDERS`'ga qo'shing.

**Xavfsizlik va cheklovlar:**
- Audio faqat HTTPS orqali, `BASE_URL` hosti yoki `ALLOWED_HOSTS`'dan yuklanadi. Redirect ham tekshiriladi. Boshqa manbalar bloklanadi va ularga qayta urinilmaydi.
- API kalit logga va xatolar matniga chiqmaydi.
- Telegram kanalga taxminan 20 xabar/daqiqa qabul qiladi. Import trek orasida 3,5 soniya kutadi, ya'ni soatiga ~1000 trek. `RetryAfter` hisobga olinadi.
- Bitta fayl 49 MB dan katta bo'lmasligi kerak (bot API limiti).
- Job holati `library.json` ichida saqlanadi. Server qayta ishga tushsa, `running` job'lar o'zi davom etadi.
  Render bepul tarifda server ~15 daqiqa so'rov kelmasa uxlaydi. Uyg'otish uchun botga istalgan xabar yozing.
- Xato bergan trek 3 marta qayta uriniladi, keyin `failed` bo'ladi (`/import_failed`, `/import_retry`).

## DistroKid Vault importi (o'zingizning original yozuvlaringiz)

DistroKid ommaviy katalog API'sini bermaydi. Shu sababli bot DistroKid'ga ulanmaydi va saytni o'qimaydi.
Siz Vault'dan yuklab olgan backup'larni botga yuborasiz.

1. Botga `/vault` yozing va fayllar o'zingizga tegishli ekanini **✅ Tasdiqlayman** tugmasi bilan tasdiqlang.
2. Yuboring:
   - **ZIP backup'lar.** Har biri ≤20 MB bo'lishi kerak (Telegram bot API limiti), katta backup'ni albomlarga bo'ling.
     ZIP ichidagi papka tuzilishi muhim emas, `__MACOSX`, rasm va boshqa fayllar o'tkazib yuboriladi.
   - **alohida audio** (MP3, M4A, WAV, FLAC, AIFF, OGG). 20 MB dan katta MP3/M4A ham qabul qilinadi.
   - **CSV metadata** (ixtiyoriy): `title, artist`, qo'shimcha `isrc, album, file, duration`.
   - `/vault_folder yo'l`: serverdagi `IMPORT_ROOT` ichidagi papka (doimiy disk bo'lsa).
   - `/vault_artist Ism`: ijrochi topilmagan fayllar uchun standart ijrochi.
3. **▶️ Importni boshlash** tugmasini bosing.

**Moslash tartibi:** CSV'dagi ISRC → `file` ustuni → ijrochi+nom → nom (bitta nomzod bo'lsa)
→ o'xshash nom (faqat bitta aniq nomzod bo'lsa). Qiymatlar quyidagi ustuvorlikda olinadi: CSV, keyin audio teglari, keyin fayl nomi
(`01 - Ijrochi - Nomi`, `Nomi (ISRC)`). Moslab bo'lmagan fayllar **🏷 Mos kelmaganlar** ro'yxatida ko'rinadi.

**Takrorlar** sha256 bo'yicha aniqlanadi: ZIP ichida, sessiyada va bazada. Qo'shimcha ravishda ISRC va ijrochi+nom+davomiylik ham tekshiriladi.
Bir backup'ni ikki marta import qilsangiz, hech narsa qayta yuklanmaydi.

**Saqlash:** fayl kutubxona kanaliga yuklanadi va bazaga `file_id` bilan yoziladi. Qidiruv va yetkazish avvalgidek ishlaydi.
WAV, FLAC, AIFF va OGG fayllar MP3 320k ga o'giriladi. Bazaga `sha256`, `isrc`, `album`, `source_file` va `license_id`
(`own-master:vault-job-N`) yoziladi. `ARCHIVE_DIR` berilsa, originallar o'sha papkaga sha256 nomi bilan saqlanadi.
Buning uchun doimiy disk kerak (Render Disk). Bepul tarifda bu disk har deploy'da tozalanadi.

**Progress ekrani:** foiz, qo'shilgan/bazada bor/xato/navbatda/metadata yo'q soni, metadata manbalari, qolgan vaqt.
Tugmalari: ⏸ Pauza, ▶️ Davom, 🔄 Yangilash, 📋 Xatolar, 🏷 Mos kelmaganlar, ⏭ Yakunlash, ❌ Bekor.
`/imports` barcha import'larni ko'rsatadi.

**Resume:** job holati indeksda saqlanadi. Server qayta yonsa, ZIP Telegram'dan `file_id` orqali qayta yuklanadi
va import qolgan joyidan davom etadi. Yuklangan treklar qayta yuklanmaydi.

## Free Music Archive (CC litsenziyali katalog)

**Manba:** rasmiy [FMA dataset](https://github.com/mdeff/fma) (2017 snapshot, 106 574 trek).
`fma_metadata.zip` ichidagi `tracks.csv` va `fma_full.zip` (kesilmagan MP3, 879 GiB) ishlatiladi.
Bot FMA saytiga ham, API'siga ham murojaat qilmaydi. Fayllarni server egasi dataset'ning rasmiy manzilidan yuklab,
`IMPORT_ROOT` ichiga qo'yadi. `fma_full.zip`'ni ochish shart emas.

```
IMPORT_ROOT=/data/imports
FMA_METADATA=fma_metadata/tracks.csv   # IMPORT_ROOT'ga nisbatan
FMA_AUDIO=fma_full                      # yoki fma_full.zip
BOT_COMMERCIAL=1                        # standart: bot reklamali => NC treklar chiqarib tashlanadi
FMA_GENRES=Pop,Hip-Hop,Soul-RnB,Rock,Electronic,Jazz,Classical,Folk,International   # standart; "all" = hammasi
FMA_LANGUAGES=                          # bo'sh = filtrsiz; masalan "uz,ru,en"
FMA_TARGET=50000
```

**Litsenziya siyosati** (`importer/licenses.py`). Har bir trek alohida tekshiriladi:
- ✅ CC0, Public Domain Mark, CC BY, CC BY-SA
- ✅ CC BY-ND, faqat o'zgartirilmagan holda. FMA MP3'lari aynan o'zi yuboriladi: kesilmaydi, qayta kodlanmaydi.
- ❌ NonCommercial. Bot tijoriy bo'lsa (`BOT_COMMERCIAL=1`) rad etiladi.
- ❌ Sampling+, FMA-Limited, "All rights reserved", noma'lum yoki bo'sh litsenziya.
- ❌ audio fayli yo'q yoki 49 MB dan katta (o'zgartirmasdan yuborib bo'lmaydi).

**Muallifni ko'rsatish.** Har bir trek bilan bazaga quyidagilar yoziladi: muallif, `artist_url`, litsenziya nomi, `license_url`,
`license_code`, manba (Free Music Archive, trek ID, dataset URL), til va janr. Foydalanuvchiga yuborilganda caption'da
«Nom» — Ijrochi. Manba. Litsenziya (URL) matni ko'rsatiladi.
`tracks.csv`'da trek sahifasining URL'i yo'q, uni taxmin qilib qo'ymaymiz. Port (yurisdiksiya) noma'lum bo'lsa,
litsenziya URL'i bo'sh qoladi va faqat nomi ko'rsatiladi.

**Metadata hisoboti (audio'siz):**
```bash
python -m importer.fma_report /yo'l/fma_metadata --out fma_report   # --noncommercial — NC ham
```
`tracks.csv` (asosiy ro'yxat), `raw_tracks.csv` (FMA bergan `license_url` va `track_url`) va `genres.csv` o'qiladi.
Natija `fma_report.md` va `fma_report.json` (yaroqli treklar ro'yxati) fayllariga yoziladi. Oxirgi hisobot: [reports/fma_metadata_report.md](reports/fma_metadata_report.md).

**Bittalab tekshirish va manifest:**
```bash
python -m importer.fma_verify /yo'l/fma_metadata arxiv_index.json checksums.txt --out fma_verified_tracks.csv
```
Har bir trek uchun litsenziya nomi va URL'i alohida solishtiriladi, siyosat tekshiriladi, audio mavjudligi va hajmi
`fma_full.zip`'ning fayl ro'yxatidan, butunligi esa rasmiy `checksums` bo'yicha tekshiriladi. Bu ma'lumotlar HTTP Range orqali olinadi
(~20 MB), butun arxiv yuklanmaydi. Natija [reports/fma_verification_report.md](reports/fma_verification_report.md),
manifest `reports/fma_verified_tracks.csv.gz` (bot shundan o'qiydi), test ro'yxati `reports/fma_test_batch.json`.
Faqat `verified` holatidagi treklar yuklanadi.

**Huquqi noaniq deb belgilanadigan treklar** (yuklanmaydi): arxiv to'plamlari (masalan, Excavated Shellac: eski 78 rpm
plastinkalar, yuklovchi huquq egasi emas), tavsifida tarixiy yozuv belgilari bor treklar va Public Domain Mark
(belgi, litsenziya emas).

**Muvofiqlik:** FMA treklari o'zgartirilmasdan yuboriladi. Yuklashdan oldin rasmiy sha1, yuklagandan keyin
Telegram'dagi nusxaning sha1'i tekshiriladi va farq bo'lsa trek o'chiriladi. Kanal posti va foydalanuvchiga yuboriladigan
audio caption'ida atribusiya bo'ladi, ostida **📜 Litsenziya**, **🔗 Manba** va **ℹ️ Ma'lumot** tugmalari turadi.
`protect_content=False` aniq beriladi. Test rejimida litsenziya va manba sahifalari jonli tekshiriladi.
Hisobot: [reports/fma_test_compliance_report.md](reports/fma_test_compliance_report.md).

**Test importi:** botda `/fma_test` → **▶️ Importni boshlash**. 20 ta trek rasmiy arxivdan Range bilan olinadi,
sha1 tekshiriladi va o'zgartirilmasdan kanalga yuboriladi. **📋 Natijalar** tugmasi har bir trekning holatini ko'rsatadi, **📄 Muvofiqlik hisoboti** esa CSV va xulosa yuboradi.
Butun katalog importi test natijalari ko'rib chiqilgandan keyin alohida yoqiladi.

**Jarayon** (`/fma`):
1. **🔢 Katalogni sanash.** Butun `tracks.csv` o'qiladi, hech narsa yuklanmaydi. Hisobotda quyidagilar bo'ladi: nechta yaroqli trek bor,
   50 000 maqsadga **yetadimi yoki yo'qmi**, litsenziya, janr va til bo'yicha taqsimot, rad etish sabablari.
2. **▶️ Importni boshlash.** Faqat yaroqli treklar, batch bilan, pauza/davom qilish mumkin. Takrorlar FMA ID,
   sha256 va ijrochi+nom+davomiylik bo'yicha aniqlanadi. Server qayta yonsa, import o'zi davom etadi.

**Masshtab va cheklovlar:**
- Indeks v3: manifest va 2000 tadan bo'laklar. 50 000 trek ≈ 25 bo'lak × ~2 MB. Saqlashda faqat o'zgargan bo'lak yoziladi.
- Telegram kanalga ~20 xabar/daqiqa: 50 000 trek ≈ **55–60 soat** uzluksiz yuklash.
- `fma_full` 879 GiB. Uni saqlash uchun katta diskli server (VPS) kerak, Render bepul tarifi yetmaydi. Bunda bot
  o'sha serverda ishlashi kerak: indeksni bitta jarayon yozadi.
- 50 000 trekli indeks xotirada ~200–300 MB egallaydi. Render bepul tarifida bu 512 MB limitga yaqin.
- Dataset 2017 yilgi. CC litsenziyalari qaytarib olinmaydi, lekin muhim treklarni joriy FMA sahifasida tekshirib ko'rish tavsiya etiladi.

## Testlar

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q tests
```
