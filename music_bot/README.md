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

## Testlar

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q tests
```
