"""All user-facing Uzbek (Latin) strings."""

START = (
    "👋 <b>Salom!</b>\n\n"
    "Men quyidagilarni qila olaman:\n"
    "🎬 <b>Video yuklash</b> — Instagram Reels, TikTok, YouTube va boshqa ochiq havolalar\n"
    "🎵 <b>Qo'shiq aniqlash</b> — video, audio yoki ovozli xabar yuboring\n"
    "🔎 <b>Qo'shiq qidirish</b> — nomi yoki ijrochisini yozing\n\n"
    "Boshlash uchun havola yuboring yoki pastdagi tugmalardan foydalaning 👇"
)

HELP = (
    "ℹ️ <b>Yordam</b>\n\n"
    "• <b>Video yuklash:</b> havolani yuboring, so'ng «🎬 Video» yoki «🎵 MP3» ni tanlang.\n"
    "• <b>Qo'shiq aniqlash:</b> video, audio fayl yoki ovozli xabar yuboring.\n"
    "• <b>Qidirish:</b> qo'shiq nomi yoki ijrochisini yozing, masalan: <code>Shahzoda Ko'zlaring</code>.\n\n"
    "⚠️ Faqat ochiq (public) kontent yuklanadi. Shaxsiy akkauntlar, DRM bilan himoyalangan "
    "yoki kirish talab qiladigan materiallar qo'llab-quvvatlanmaydi.\n"
    "📦 Telegram cheklovi: yuklab olinadigan fayl 50 MB gacha; yuborgan fayllaringiz 20 MB gacha.\n"
    "© Faqat o'zingiz foydalanish huquqiga ega kontentni yuklang."
)

BTN_SEARCH = "🔎 Qo'shiq qidirish"
BTN_IDENTIFY = "🎵 Qo'shiq aniqlash"
BTN_HELP = "ℹ️ Yordam"

SEARCH_PROMPT = "🔎 Qo'shiq nomi yoki ijrochisini yozing:"
IDENTIFY_PROMPT = "🎵 Video, audio fayl yoki ovozli xabar yuboring — qo'shiqni aniqlayman."

CHOOSE_ACTION = "🔗 Havola qabul qilindi. Nima qilamiz?"
BTN_VIDEO = "🎬 Video"
BTN_MP3 = "🎵 MP3"
BTN_RECOGNIZE = "🔍 Qo'shiqni aniqlash"
BTN_CANCEL = "✖️ Bekor qilish"

EXPIRED = "⌛ Havola eskirgan. Iltimos, uni qaytadan yuboring."
QUEUED = "⏳ Navbatda... biroz kuting."
DOWNLOADING = "⬇️ Yuklab olinmoqda..."
CONVERTING = "⚙️ Ishlov berilmoqda..."
UPLOADING = "📤 Yuborilmoqda..."
IDENTIFYING = "🎧 Tinglanmoqda..."
SEARCHING = "🔎 Qidirilmoqda..."
CANCELLED = "Bekor qilindi."

ERR_BAD_URL = "❌ Bu havola qo'llab-quvvatlanmaydi yoki xavfsiz emas."
ERR_DOWNLOAD = (
    "❌ Yuklab bo'lmadi. Sabablari: akkaunt yopiq, kontent o'chirilgan, platforma kirishni talab qiladi "
    "yoki sayt hozircha qo'llab-quvvatlanmaydi."
)
ERR_TOO_BIG = "❌ Fayl Telegram cheklovidan (50 MB) katta. Qisqaroq video tanlang yoki «🎵 MP3» ni sinab ko'ring."
ERR_INPUT_TOO_BIG = "❌ Telegram botlar 20 MB dan katta fayllarni yuklab ola olmaydi. Qisqaroq qismini yuboring."
ERR_NO_AUDIO = "❌ Faylda ovoz topilmadi."
ERR_GENERIC = "❌ Kutilmagan xatolik yuz berdi. Keyinroq qayta urinib ko'ring."
ERR_RECOGNITION_OFF = (
    "⚠️ Qo'shiq aniqlash hozircha sozlanmagan (bot egasi API kalitini kiritmagan). "
    "Qidirish va video yuklash ishlaydi."
)
ERR_RECOGNITION_API = "❌ Aniqlash xizmati javob bermadi. Keyinroq qayta urinib ko'ring."
NOT_FOUND_SONG = "😕 Qo'shiq aniqlanmadi. Musiqa aniqroq eshitiladigan 10–20 soniyalik qismini yuboring."
NOT_FOUND_SEARCH = "😕 Hech narsa topilmadi. Boshqacha yozib ko'ring."
ERR_SEARCH = "❌ Qidiruv xizmati javob bermadi. Keyinroq urinib ko'ring."


def track_card(title: str, artist: str, album: str | None = None) -> str:
    from html import escape

    lines = ["✅ <b>Topildi!</b>", "", f"🎶 <b>{escape(title)}</b>", f"👤 {escape(artist)}"]
    if album:
        lines.append(f"💿 {escape(album)}")
    return "\n".join(lines)
