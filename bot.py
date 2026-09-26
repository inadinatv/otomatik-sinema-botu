"""FullHDFilmizlesene.now film kataloglayıcı ve Telegram bildirim botu.

Site, oynatıcı iframe'ini ilk HTML'de vermiyor. Film sayfasındaki `scx` nesnesinin
`sx.p` / `sx.t` alanlarında ROT13+Base64 ile kodlanmış, sitenin kendi yayınladığı
embed URL'leri bulunuyor. Bu dosya yalnızca bu açık metadata'yı çözer; CAPTCHA,
Cloudflare veya erişim kontrolü aşmaya çalışmaz ve medya akışını indirmez.
"""

from __future__ import annotations

import base64
import codecs
import json
import logging
import os
import re
import time
from dataclasses import dataclass, asdict
from html import unescape
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from curl_cffi import requests

BASE_URL = os.getenv("FILM_SITE_URL", "https://www.fullhdfilmizlesene.now").rstrip("/")
DB_FILE = Path(os.getenv("DB_FILE", "veritabani.json"))
REQUEST_DELAY = float(os.getenv("REQUEST_DELAY", "1.0"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
MAX_PAGES_PER_CATEGORY = int(os.getenv("MAX_PAGES_PER_CATEGORY", "0"))

KATEGORILER = {
    "Yeni Filmler": "/yeni-filmler/",
    "Aile Filmleri": "/filmizle/aile-filmleri/",
    "Aksiyon Filmleri": "/filmizle/aksiyon-filmleri/",
    "Animasyon Filmleri": "/filmizle/animasyon-filmleri/",
    "Bilim Kurgu Filmleri": "/filmizle/bilim-kurgu-filmleri/",
    "Dram Filmleri": "/filmizle/dram-filmleri/",
    "Fantastik Filmler": "/filmizle/fantastik-filmleri/",
    "Gerilim Filmleri": "/filmizle/gerilim-filmleri/",
    "Komedi Filmleri": "/filmizle/komedi-filmleri/",
    "Korku Filmleri": "/filmizle/korku-filmleri/",
    "Macera Filmleri": "/filmizle/macera-filmleri/",
    "Romantik Filmler": "/filmizle/romantik-filmleri/",
    "Yerli Filmler": "/filmizle/yerli-filmler/",
}

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sinema-botu")


class SiteAccessBlocked(RuntimeError):
    """Site erişim kontrolü uyguladığında taramayı durdurmak için kullanılır."""

session = requests.Session(impersonate="chrome120")
session.headers.update({
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
    "User-Agent": "SinemaKatalogBot/2.0 (+respectful catalog reader)",
})


@dataclass
class Film:
    id: int
    baslik: str
    kategori: str
    afis: str
    aciklama: str
    iframe: str
    kaynaklar: list[str]
    url: str
    sayfa: int
    imdb: str = ""
    yil: str = ""
    kalite: str = "HD"


def absolute_url(value: str, base: str = BASE_URL) -> str:
    value = unescape((value or "").strip().replace("\\/", "/"))
    if value.startswith("//"):
        return "https:" + value
    return urljoin(base + "/", value)


def clean_title(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return re.sub(r"\s+(?:izle|full hd izle|hd izle)$", "", value, flags=re.I).strip()


def decode_rot13_base64(value: str) -> str | None:
    """Site player kodlaması: ROT13 metin -> Base64 -> UTF-8."""
    if not isinstance(value, str) or len(value) < 8:
        return None
    try:
        rotated = codecs.decode(value.strip(), "rot_13")
        raw = base64.b64decode(rotated + "=" * (-len(rotated) % 4), validate=False)
        return raw.decode("utf-8", errors="ignore").strip()
    except (ValueError, UnicodeError, base64.binascii.Error):
        return None


def iframe_from_markup(value: str) -> str | None:
    if not value:
        return None
    value = unescape(value).replace("\\/", "/").strip()
    if value.startswith("//"):
        return "https:" + value
    if value.startswith("http://") or value.startswith("https://"):
        return value
    match = re.search(r"<iframe[^>]+(?:src|data-src)=[\"']([^\"']+)", value, re.I)
    return absolute_url(match.group(1)) if match else None


def valid_embed_url(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except ValueError:
        return False


def extract_scx_sources(html: str) -> list[str]:
    """scx içindeki tüm public player kaynaklarını sırayla döndürür."""
    match = re.search(r"var\s+scx\s*=\s*(\{.*?\})\s*;", html, flags=re.S)
    if not match:
        return []
    try:
        scx: dict[str, Any] = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    decoded: list[str] = []
    for source in scx.values():
        if not isinstance(source, dict):
            continue
        sx = source.get("sx", {})
        if not isinstance(sx, dict):
            continue
        for group in (sx.get("p", []), sx.get("t", [])):
            if isinstance(group, dict):
                values: Iterable[Any] = group.values()
            elif isinstance(group, list):
                values = group
            else:
                continue
            for encoded in values:
                candidate = decode_rot13_base64(encoded)
                candidate = iframe_from_markup(candidate or "")
                if valid_embed_url(candidate) and candidate not in decoded:
                    decoded.append(candidate)
    return decoded


def page_description(soup: BeautifulSoup) -> str:
    node = soup.select_one(".film-ozeti .ozet-ic, .film-ozeti, [itemprop='description']")
    if node:
        text = " ".join(node.stripped_strings)
        if len(text) >= 10:
            return text
    meta = soup.select_one("meta[name='description']")
    return (meta.get("content", "").strip() if meta else "") or "Bu film için açıklama bulunamadı."


def fetch_html(url: str) -> str:
    time.sleep(REQUEST_DELAY)
    response = session.get(url, timeout=25)
    if response.status_code in {401, 403, 429}:
        raise SiteAccessBlocked(
            f"Site erişimi kısıtladı (HTTP {response.status_code}). "
            "Koruma aşılmayacak; tarama güvenli biçimde durduruldu."
        )
    response.raise_for_status()
    challenge_markers = ("just a moment", "cf-chl-", "cloudflare ray id")
    if any(marker in response.text.lower() for marker in challenge_markers):
        raise SiteAccessBlocked(
            "Cloudflare doğrulama sayfası döndü. Koruma aşılmayacak; tarama durduruldu."
        )
    return response.text


def extract_movie_data(film_url: str) -> dict[str, Any]:
    try:
        html = fetch_html(film_url)
        soup = BeautifulSoup(html, "html.parser")
        sources = extract_scx_sources(html)
        return {
            "aciklama": page_description(soup),
            "iframe": sources[0] if sources else None,
            "kaynaklar": sources,
            "hata": None if sources else "scx içinden oynatıcı kaynağı bulunamadı",
        }
    except SiteAccessBlocked:
        raise
    except Exception as exc:
        log.warning("Film okunamadı %s: %s", film_url, exc)
        return {"aciklama": "Veri alınamadı.", "iframe": None, "kaynaklar": [], "hata": str(exc)}


def extract_cards(soup: BeautifulSoup, category: str, page: int) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    seen: set[str] = set()
    for card in soup.select(".film"):
        link = card.select_one("a.tt[href*='/film/']") or card.select_one("a[href*='/film/']")
        if not link:
            continue
        url = absolute_url(link.get("href", ""))
        if url in seen:
            continue
        seen.add(url)
        title_node = card.select_one(".film-title") or card.select_one("h2") or link
        img = card.select_one("img")
        imdb = card.select_one(".imdb")
        yil = card.select_one(".film-yil")
        kalite = card.select_one(".hd, .uhd")
        poster = ""
        if img:
            poster = img.get("data-src") or img.get("src") or ""
            if poster.startswith("data:"):
                poster = img.get("data-srcset", "").split(",")[0].strip().split(" ")[0]
            poster = absolute_url(poster)
        cards.append({"baslik": clean_title(title_node.get_text(" ", strip=True)), "url": url, "afis": poster, "kategori": category, "sayfa": page,
                      "imdb": imdb.get_text(strip=True) if imdb else "", "yil": yil.get_text(strip=True) if yil else "",
                      "kalite": kalite.get_text(strip=True) if kalite else "HD"})
    return cards


def next_page_url(soup: BeautifulSoup) -> str | None:
    tag = soup.select_one("a[rel='next'], a.next, a.next-page, a.ileri, a.sonraki")
    if not tag:
        tag = next((a for a in soup.select("a[href]") if a.get_text(" ", strip=True).lower() in {"ileri", "sonraki", "next"}), None)
    return absolute_url(tag.get("href")) if tag and tag.get("href") else None


def send_telegram(message: str) -> None:
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    try:
        response = session.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=15)
        response.raise_for_status()
    except Exception as exc:
        log.warning("Telegram bildirimi gönderilemedi: %s", exc)


def load_db() -> dict[str, Any]:
    if not DB_FILE.exists():
        return {"kategoriler": list(KATEGORILER), "filmler": []}
    try:
        return json.loads(DB_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log.warning("Veritabanı okunamadı; boş arşivle devam ediliyor")
        return {"kategoriler": list(KATEGORILER), "filmler": []}


def save_db(db: dict[str, Any]) -> None:
    tmp = DB_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(DB_FILE)


def run() -> None:
    db = load_db()
    known_urls = {film.get("url") for film in db.get("filmler", [])}
    known_titles = {film.get("baslik") for film in db.get("filmler", [])}
    added = 0

    for category, path in KATEGORILER.items():
        current = absolute_url(path)
        page = 1
        visited: set[str] = set()
        while current and current not in visited and (not MAX_PAGES_PER_CATEGORY or page <= MAX_PAGES_PER_CATEGORY):
            visited.add(current)
            try:
                soup = BeautifulSoup(fetch_html(current), "html.parser")
            except SiteAccessBlocked as exc:
                log.error("%s", exc)
                log.error("Tarama sonlandırıldı. Bir süre sonra manuel olarak tekrar deneyin.")
                return
            except Exception as exc:
                log.warning("Kategori okunamadı %s: %s", current, exc)
                break
            cards = extract_cards(soup, category, page)
            log.info("%s / sayfa %s: %s film kartı", category, page, len(cards))
            if not cards:
                break
            for card in cards:
                if card["url"] in known_urls or card["baslik"] in known_titles:
                    continue
                try:
                    details = extract_movie_data(card["url"])
                except SiteAccessBlocked as exc:
                    log.error("%s", exc)
                    log.error("Tarama sonlandırıldı; aynı engeli tekrar tekrar tetiklememek için devam edilmiyor.")
                    return
                if not details["iframe"]:
                    log.info("Atlandı (%s): %s", details["hata"], card["baslik"])
                    continue
                record = Film(id=len(db["filmler"]) + 1, baslik=card["baslik"], kategori=category, afis=card["afis"], aciklama=details["aciklama"], iframe=details["iframe"], kaynaklar=details["kaynaklar"], url=card["url"], sayfa=page, imdb=card["imdb"], yil=card["yil"], kalite=card["kalite"])
                db["filmler"].append(asdict(record))
                known_urls.add(card["url"])
                known_titles.add(card["baslik"])
                added += 1
                save_db(db)
                log.info("Eklendi: %s", card["baslik"])
            current = next_page_url(soup)
            page += 1

    if added:
        send_telegram(f"<b>Sinema botu güncellendi</b>\n\nYeni oynatıcılı film: {added}\nToplam arşiv: {len(db['filmler'])}")
    log.info("Tamamlandı: %s yeni film, toplam %s", added, len(db["filmler"]))


if __name__ == "__main__":
    run()
