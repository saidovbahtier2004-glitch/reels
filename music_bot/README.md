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
