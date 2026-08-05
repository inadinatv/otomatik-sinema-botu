import json
import os
import re
import base64
import codecs
import time
import random
from pathlib import Path
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
from curl_cffi import requests

# ==========================================
# ⚙️ SİSTEM AYARLARI
# ==========================================
BASE_URL = "https://fullhdfilmizlesene.co"
DB_FILE = "veritabani.json"

# Güvenlik: Hassas bilgileri ortam değişkenlerinden al
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

KATEGORILER = {
    "Aile Filmleri": "/filmizle/aile-filmleri/",
    "Aksiyon Filmleri": "/filmizle/aksiyon-filmleri/",
    "Animasyon Filmleri": "/filmizle/animasyon-filmleri/",
    "Belgeseller": "/filmizle/belgeseller/",
    "Bilim Kurgu Filmleri": "/filmizle/bilim-kurgu-filmleri/",
    "Blu Ray Filmler": "/filmizle/bluray-filmler/",
    "Çizgi Filmler": "/filmizle/cizgi-filmler/",
    "Dram Filmleri": "/filmizle/dram-filmleri/",
    "Fantastik Filmler": "/filmizle/fantastik-filmler/",
    "Gerilim Filmleri": "/filmizle/gerilim-filmleri/",
    "Gizem Filmleri": "/filmizle/gizem-filmleri/",
    "Hint Filmleri": "/filmizle/hint-filmleri/",
    "Komedi Filmleri": "/filmizle/komedi-filmleri/",
    "Korku Filmleri": "/filmizle/korku-filmleri/",
    "Macera Filmleri": "/filmizle/macera-filmleri/",
    "Müzikal Filmler": "/filmizle/muzikal-filmler/",
    "Polisiye Filmleri": "/filmizle/polisiye-filmleri/",
    "Psikolojik Filmler": "/filmizle/psikolojik-filmler/",
    "Romantik Filmler": "/filmizle/romantik-filmler/",
    "Savaş Filmleri": "/filmizle/savas-filmleri/",
    "Suç Filmleri": "/filmizle/suc-filmleri/",
    "Tarih Filmleri": "/filmizle/tarih-filmleri/",
    "Western Filmler": "/filmizle/western-filmler/",
    "Yerli Filmler": "/filmizle/yerli-filmler/"
}

# ==========================================
# 🔥 CLOUDFLARE GEÇİŞ ÇÖZÜMLERİ
# ==========================================
# Site Cloudflare ile korunmaktadır. Aşağıdaki yöntemlerden birini kullanın:
# 
# YÖNTEM 1: FlareSolverr (Önerilen)
# ---------------------------------
# 1. Docker ile FlareSolverr çalıştırın:
#    docker run -d -p 8191:8191 flaresolverr/flaresolverr:latest
# 
# 2. FLARESOLVERR_URL ortam değişkenini ayarlayın:
#    export FLARESOLVERR_URL="http://localhost:8191"
#
# YÖNTEM 2: Selenium/Playwright ile Gerçek Tarayıcı
# --------------------------------------------------
# pip install selenium webdriver-manager
# veya
# pip install playwright && playwright install chromium
#
# YÖNTEM 3: Manuel Cookie Ekleme
# ------------------------------
# 1. Tarayıcınızda siteyi açın ve Cloudflare'i geçin
# 2. Developer Tools > Application > Cookies bölümünden
#    __cf_bm, cf_clearance gibi cookie'leri kopyalayın
# 3. Ortam değişkeni olarak ekleyin:
#    export CF_COOKIE="__cf_bm=xxx; cf_clearance=yyy"
# ==========================================

FLARESOLVERR_URL = os.getenv("FLARESOLVERR_URL", "")

# Session yapılandırması - Cloudflare bypass için en güncel Chrome sürümü
session = requests.Session(impersonate="chrome124")

# Sitenin bizi gerçek bir Chrome kullanıcısı sanması için gelişmiş Header'lar
HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": BASE_URL + "/"
}
session.headers.update(HEADERS)

# Manuel cookie ekleme (eğer ortam değişkeni varsa)
CF_COOKIE = os.getenv("CF_COOKIE", "")
if CF_COOKIE:
    session.cookies.update({"cf_clearance": CF_COOKIE})

def telegram_mesaj_gonder(mesaj: str) -> None:
    """Telegram bot üzerinden mesaj gönderir."""
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj, "parse_mode": "HTML"}
        session.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram mesaj hatası: {e}")


def baslik_temizle(baslik: str) -> str:
    """Film başlığını gereksiz ifadelerden temizler."""
    silinecek_kelimeler = [
        " Türkçe Dublaj İzle", " Türkçe Dublaj", " Full HD İzle", 
        " HD İzle", " 1080p İzle", " Altyazılı İzle", " izle"
    ]
    for kelime in silinecek_kelimeler:
        baslik = re.sub(kelime, "", baslik, flags=re.IGNORECASE)
    return baslik.strip()


def gecerli_oynatici_mi(url: str) -> bool:
    """URL'nin geçerli bir video oynatıcı olup olmadığını kontrol eder."""
    if not url or len(url) < 10:
        return False
    
    url_low = url.lower().replace("\\/", "/")
    
    yasakli_uzantilar = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js", ".xml", ".woff", ".ttf", ".ico"]
    if any(uzanti in url_low for uzanti in yasakli_uzantilar):
        return False
    
    yasakli_siteler = ["youtube.com", "youtu.be", "vimeo", "fragman", "google.com", "facebook.com", "twitter.com", "imdb.com", "themoviedb.org", "w3.org", "analytics"]
    if any(yasak in url_low for yasak in yasakli_siteler):
        return False
    
    gecerli_sunucular = [
        "trstx", "vidmoly", "rapidvid", "embed", "player", "vod", "play", 
        "video", "iframe", "proton", "fast", "stream", "cdn", "hdpass", 
        "netu", "watch", "ok.ru", "mail.ru", "vk.com", "uqload", "dood",
        "filemoon", "vtube", "mixdrop", "uptobox"
    ]
    if any(gecerli in url_low for gecerli in gecerli_sunucular):
        return True
    return False


def decode_iframe(s: str) -> Optional[str]:
    """Base64 veya ROT13 kodlu iframe URL'lerini çözer."""
    if not isinstance(s, str) or len(s) < 10:
        return None
    
    s = s.strip()
    s_pad = s + '=' * (-len(s) % 4)
    
    for method in ['rot13_b64', 'b64']:
        try:
            if method == 'rot13_b64':
                dec = base64.b64decode(codecs.encode(s_pad, 'rot_13')).decode('utf-8', errors='ignore')
            else:
                dec = base64.b64decode(s_pad).decode('utf-8', errors='ignore')
            
            if "http" in dec or dec.startswith("//"):
                temiz_link = dec.replace("\\/", "/")
                if temiz_link.startswith("//"):
                    temiz_link = "https:" + temiz_link
                if gecerli_oynatici_mi(temiz_link):
                    return temiz_link
        except Exception:
            pass
    return None

def flaresolverr_request(url: str, method: str = "GET") -> Optional[Any]:
    """FlareSolverr kullanarak Cloudflare korumalı siteye istek yapar."""
    if not FLARESOLVERR_URL:
        return None
    
    try:
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": 60000,
            "session": "film_bot_session"
        }
        
        resp = requests.post(FLARESOLVERR_URL, json=payload, timeout=60)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "ok":
                return data.get("solution", {}).get("response")
    except Exception as e:
        print(f"  [!] FlareSolverr hatası: {e}")
    return None


def extract_movie_data(film_url):
    try:
        # IP BAN YEMEMEK İÇİN ZORUNLU BEKLEME
        time.sleep(random.uniform(1.5, 3.0)) 
        
        # Önce FlareSolverr ile dene (eğer yapılandırılmışsa)
        html_content = None
        if FLARESOLVERR_URL:
            response = flaresolverr_request(film_url)
            if response:
                html_content = response
        
        # FlareSolverr yoksa veya başarısız olduysa normal istek yap
        if not html_content:
            req = session.get(film_url, timeout=15)
            
            if req.status_code in [403, 401, 429, 502, 503]:
                # Cloudflare engeli varsa tekrar FlareSolverr dene
                if FLARESOLVERR_URL:
                    response = flaresolverr_request(film_url)
                    if response:
                        html_content = response
                    else:
                        return {"aciklama": "", "iframe": None, "hata": f"Güvenlik Engeli (Kod: {req.status_code})"}
                else:
                    return {"aciklama": "", "iframe": None, "hata": f"Güvenlik Engeli (Kod: {req.status_code})"}
            
            if not html_content:
                html_content = req.text.replace("\\/", "/")
        else:
            html_content = html_content.replace("\\/", "/")

        soup = BeautifulSoup(html_content, 'html.parser')
        
        sayfa_metni = html_content.lower()
        yasakli_durumlar = ["yapım aşamasında", "henüz sitemize eklenmemiştir", "yakında sinemalarda", "telif hakkı nedeniyle kaldırılmıştır"]
        for durum in yasakli_durumlar:
            if durum in sayfa_metni: return {"aciklama": "", "iframe": None, "hata": "Yapım Aşamasında / Telif Yemiş"}

        aciklama = ""
        ozet_div = soup.select_one(".ozet, .summary, .film-content, .film-ozeti, div[itemprop='description'], p[itemprop='description'], .film_detay_icerik")
        if ozet_div: aciklama = ozet_div.text.strip()
        if not aciklama or len(aciklama) < 10:
            paragraphs = soup.select('article p, .post-content p, .film-detail-content p')
            if paragraphs: aciklama = " ".join([p.text.strip() for p in paragraphs if len(p.text.strip()) > 15])
        if not aciklama or len(aciklama) < 10:
            meta_desc = soup.select_one('meta[name="description"]')
            if meta_desc: aciklama = meta_desc.get("content", "").strip()
        if not aciklama: aciklama = "Bu film için açıklama bulunamadı."

        iframe_linki = None
        
        # Iframe'leri bul - daha geniş seçiciler
        for iframe in soup.find_all('iframe'):
            olasi_kaynaklar = [iframe.get('data-src'), iframe.get('src'), iframe.get('data-url'), iframe.get('data-link')]
            for kaynak in olasi_kaynaklar:
                if kaynak and ("http" in kaynak or kaynak.startswith("//")):
                    temiz_link = kaynak if kaynak.startswith("http") else "https:" + kaynak
                    if gecerli_oynatici_mi(temiz_link):
                        iframe_linki = temiz_link
                        break
            if iframe_linki: break

        # Data attribute'larında kodlanmış linkleri ara
        if not iframe_linki:
            for tag in soup.find_all(True):
                for attr, val in tag.attrs.items():
                    if isinstance(val, str) and len(val) > 10 and attr.startswith("data-") and " " not in val:
                        dec = decode_iframe(val)
                        if dec and gecerli_oynatici_mi(dec):
                            iframe_linki = dec
                            break
                if iframe_linki: break

        # Base64 kodlu string'leri dene
        if not iframe_linki:
            base64_adaylari = set(re.findall(r'[\"\']([a-zA-Z0-9+/=]{40,})[\"\']', html_content))
            for b64 in base64_adaylari:
                dec = decode_iframe(b64)
                if dec and gecerli_oynatici_mi(dec):
                    iframe_linki = dec
                    break

        # JavaScript içindeki URL'leri ara
        if not iframe_linki:
            js_urls = re.findall(r'(?:var|let|const)\s+\w+\s*=\s*[\"\']([^\"\']+?//[^\"\']+)[\"\']', html_content)
            for url in js_urls:
                temiz_url = url.replace("\\/", "/")
                if gecerli_oynatici_mi(temiz_url):
                    iframe_linki = temiz_url
                    break

        if not iframe_linki: return {"aciklama": aciklama, "iframe": None, "hata": "Oynatıcı Bulunamadı"}
        return {"aciklama": aciklama, "iframe": iframe_linki, "hata": None}
    except Exception as e:
        return {"aciklama": "Veri alınamadı.", "iframe": None, "hata": f"Bağlantı Hatası: {e}"}

def bot_calistir():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f: veritabani = json.load(f)
    else: veritabani = {"kategoriler": list(KATEGORILER.keys()), "filmler": []}

    mevcut_basliklar = [film["baslik"] for film in veritabani.get("filmler", [])]
    genel_toplam_yeni_film = 0 
    
    print("\n" + "="*50)
    print("🚀 İNADINA TV - BOT (Güncel Domain: .mx - Proxy Kapalı)")
    print("="*50)
    
    for kategori_adi, url_yolu in KATEGORILER.items():
        kategori_yeni_film_sayisi = 0
        print(f"\n📁 [KATEGORİ BAŞLADI]: {kategori_adi} taranıyor...")
        
        sayfa = 1
        hedef_url = BASE_URL + url_yolu
        gercek_kategori_linki = hedef_url
        
        while True:
            try:
                time.sleep(random.uniform(2.0, 3.5))
                req = session.get(hedef_url, timeout=20)
                
                if req.status_code in [403, 401, 429, 502, 503]:
                    print(f"  [!!!] DİKKAT: IP Adresiniz Geçici Olarak Engellendi! (Durum Kodu: {req.status_code})")
                    print("  [!!!] Cloudflare bot olduğumuzu anladı. 60 Saniye bekleniyor...")
                    time.sleep(60)
                    continue 
                
                if req.status_code == 404: break

                soup = BeautifulSoup(req.content, 'html.parser')
                
                # EN GENİŞ HTML SEÇİCİLERİ EKLENDİ
                film_listesi = soup.select("li.film, div.movie-item, article.film, .movie-list li, .film-box, .film-card, .list-movie, div.item, div.poster, .movie")
                
                if not film_listesi: 
                    if "Cloudflare" in req.text or "Just a moment..." in req.text:
                        print("  [!!!] HATA: Cloudflare İnsan Doğrulaması (Captcha) Ekranı Çıktı.")
                        break
                    break

                print(f"  📄 Sayfa {sayfa} taranıyor... (İncelenen film: {len(film_listesi)})")
                
                for li in film_listesi:
                    # BAŞLIK SEÇİCİLERİ GENİŞLETİLDİ
                    baslik_elem = li.select_one("span.film-title, h2.title, a.title, .film-name, h3, h2, .name, .baslik")
                    ham_baslik = baslik_elem.text.strip() if baslik_elem else ""
                    
                    if not ham_baslik:
                        # Eğer class içinde bulamazsa a etiketinin title özelliğinden çekmeyi dener
                        a_tag = li.select_one("a")
                        if a_tag and a_tag.get("title"):
                            ham_baslik = a_tag.get("title").strip()
                            
                    if not ham_baslik: continue
                    baslik = baslik_temizle(ham_baslik)
                    
                    if baslik in mevcut_basliklar: continue 

                    link_elem = li.select_one("a")
                    film_url = link_elem.get("href") if link_elem else ""
                    if not film_url: continue
                    if not film_url.startswith("http"): film_url = BASE_URL + film_url
                    
                    img = li.select_one("img")
                    afis = ""
                    if img:
                        afis = img.get("data-original") or img.get("data-src") or img.get("data-lazy-src") or img.get("src") or ""
                        if afis.startswith("//"): afis = "https:" + afis
                        elif afis.startswith("/") and not afis.startswith("//"): afis = BASE_URL + afis
                    
                    detay = extract_movie_data(film_url)
                    
                    if detay["iframe"]:
                        print(f"    ✅ Eklendi: {baslik}")
                        veritabani["filmler"].append({
                            "id": len(veritabani["filmler"]) + 1,
                            "baslik": baslik,
                            "kategori": kategori_adi,
                            "afis": afis,
                            "aciklama": detay["aciklama"],
                            "iframe": detay["iframe"],
                            "sayfa": sayfa 
                        })
                        mevcut_basliklar.append(baslik)
                        kategori_yeni_film_sayisi += 1
                        genel_toplam_yeni_film += 1
                        
                        # Anlık kayıt - Çökmelere karşı önlem
                        with open(DB_FILE, "w", encoding="utf-8") as f:
                            json.dump(veritabani, f, ensure_ascii=False, indent=4)
                    else:
                        print(f"    ❌ Reddedildi ({detay['hata']}): {baslik}")
                        
                sayfa += 1
                next_tag = soup.find('a', class_='next') or soup.select_one('.pagination a.next, a.next-page, a.ileri, a.sonraki, a[rel="next"]')
                if next_tag and next_tag.get('href') and len(next_tag.get('href')) > 5:
                    next_url = next_tag.get('href')
                    hedef_url = next_url if next_url.startswith('http') else (BASE_URL + next_url if next_url.startswith('/') else BASE_URL + "/" + next_url)
                else:
                    olasi_linkler = [gercek_kategori_linki + f"page/{sayfa}/", gercek_kategori_linki + f"sayfa/{sayfa}/", gercek_kategori_linki + f"sayfa-{sayfa}/"]
                    sayfa_bulundu = False
                    for link in olasi_linkler:
                        req_test = session.get(link, timeout=15)
                        if req_test.status_code == 200 and BeautifulSoup(req_test.content, 'html.parser').select("li.film, div.movie-item, article.film, .film-box, div.item"):
                            hedef_url = link
                            sayfa_bulundu = True
                            break
                    if not sayfa_bulundu: break

            except Exception as e:
                print(f"  [!] Hata: {e}")
                break
                
        print(f"✅ {kategori_adi} bitti! Toplam {kategori_yeni_film_sayisi} gerçek video çekildi.")

    if genel_toplam_yeni_film > 0:
        tg_mesaj = f"🎬 <b>İnadına TV Bot Raporu (.mx)</b>\n\n✅ <b>Tarama Tamamlandı!</b>\n🔥 <b>Eklenen Yeni Videolu Film:</b> {genel_toplam_yeni_film}\n📚 <b>Arşivdeki Toplam Film:</b> {len(veritabani['filmler'])}\n\nSistem başarıyla güncellendi! 🚀"
        telegram_mesaj_gonder(tg_mesaj)
    else:
        print("\nℹ️ Hiç yeni film bulunamadı. Veritabanı zaten güncel.")

if __name__ == "__main__":
    bot_calistir()
