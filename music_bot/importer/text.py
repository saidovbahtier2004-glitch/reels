"""Matnni qidiruv va moslashtirish uchun normallashtirish (bot va importer uchun umumiy)."""

import re


def norm(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"[ʻʼ‘’`´']", "", text)
    return re.sub(r"[^\w]+", " ", text).strip()
