import json
import os
import re
import base64
import codecs
import time
import random
from bs4 import BeautifulSoup
from curl_cffi import requests

# ==========================================
# ⚙️ SİSTEM AYARLARI
# ==========================================
BASE_URL = "https://www.fullhdfilmizlesene.life"
DB_FILE = "veritabani.json"

TELEGRAM_BOT_TOKEN = "8993203057:AAFPHppnI_GJNrsWYJA5OV7NMytpiOg7914" 
TELEGRAM_CHAT_ID = "666941331"

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

PROXY = {"http": "socks5h://127.0.0.1:40000", "https": "socks5h://127.0.0.1:40000"}
session = requests.Session(impersonate="chrome120", proxies=PROXY)
session.headers.update({
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": "https://www.google.com/"
})

# ==========================================
# 🤖 YARDIMCI FONKSİYONLAR
# ==========================================

def telegram_mesaj_gonder(mesaj):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mesaj, "parse_mode": "HTML"}
            session.post(url, json=payload, timeout=10)
        except: pass

def baslik_temizle(baslik):
    silinecek_kelimeler = [" Türkçe Dublaj İzle", " Türkçe Dublaj", " Full HD İzle", " HD İzle", " 1080p İzle", " Altyazılı İzle", " izle"]
    for kelime in silinecek_kelimeler:
        baslik = re.sub(kelime, "", baslik, flags=re.IGNORECASE)
    return baslik.strip()

def decode_iframe(s):
    if not isinstance(s, str) or len(s) < 10: return None
    s = s.strip()
    if s.startswith("//"): return "https:" + s
    if s.startswith("http"): return s
    s_pad = s + '=' * (-len(s) % 4)
    for method in ['rot13_b64', 'b64']:
        try:
            dec = base64.b64decode(codecs.encode(s_pad, 'rot_13')).decode('utf-8') if method == 'rot13_b64' else base64.b64decode(s_pad).decode('utf-8')
            if "http" in dec and ("vod" in dec or "embed" in dec or "player" in dec or "video" in dec): 
                return dec.replace("\\/", "/")
        except: pass
    return None

def extract_movie_data(film_url):
    try:
        req = session.get(film_url, timeout=15)
        soup = BeautifulSoup(req.text, 'html.parser')
        
        aciklama = ""
        ozet_div = soup.select_one(".ozet, .summary, .film-content, .film-ozeti, div[itemprop='description'], p[itemprop='description']")
        if ozet_div: aciklama = ozet_div.text.strip()
        if not aciklama or len(aciklama) < 10:
            paragraphs = soup.select('article p, .post-content p')
            if paragraphs: aciklama = " ".join([p.text.strip() for p in paragraphs if len(p.text.strip()) > 15])
        if not aciklama or len(aciklama) < 10:
            meta_desc = soup.select_one('meta[name="description"]')
            if meta_desc: aciklama = meta_desc.get("content", "").strip()
        if not aciklama: aciklama = "Bu film için açıklama bulunamadı."

        iframe_linki = None
        
        # 1. Yöntem: SCX Şifreli Sistem
        scx_match = re.search(r'(?:scx|data)\s*=\s*(\{.*?\});', req.text)
        if scx_match:
            encoded_strings = re.findall(r"'(.*?)'", str(json.loads(scx_match.group(1))))
            for code in encoded_strings:
                dec = decode_iframe(code)
                if dec: 
                    iframe_linki = dec
                    break

        # 2. Yöntem: AHTAPOT MODU (Tüm iframe'leri süzgece takar)
        if not iframe_linki:
            for tag in soup.find_all(['iframe', 'embed']):
                val = tag.get('src') or tag.get('data-src') or tag.get('data-lazy-src')
                # İçinde youtube veya google reklamı olmayan her videoyu oynatıcı kabul et!
                if val and len(val) > 5 and 'youtube.com' not in val and 'google.com' not in val:
                    iframe_linki = "https:" + val if val.startswith('//') else val
                    break
                    
        # 3. Yöntem: En Kötü İhtimal, Regex ile Gizli Link Avlama
        if not iframe_linki:
            embed_match = re.search(r'[\"\'](https?://[^\"\']+(?:embed|v|player|video|play)[^\"\']+)[\"\']', req.text)
            if embed_match:
                iframe_linki = embed_match.group(1).replace("\\/", "/")

        return {"aciklama": aciklama, "iframe": iframe_linki}
    except:
        return {"aciklama": "Veri alınamadı.", "iframe": None}

# ==========================================
# 🚀 ANA ÇALIŞMA MOTORU
# ==========================================

def bot_calistir():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f: veritabani = json.load(f)
    else: veritabani = {"kategoriler": list(KATEGORILER.keys()), "filmler": []}

    mevcut_basliklar = [film["baslik"] for film in veritabani.get("filmler", [])]
    genel_toplam_yeni_film = 0 
    
    print("\n" + "="*50)
    print("🚀 İNADINA TV - DERİN AHTAPOT KAZICI BAŞLADI")
    print("="*50)
    
    for kategori_adi, url_yolu in KATEGORILER.items():
        kategori_yeni_film_sayisi = 0
        print(f"\n📁 [KATEGORİ BAŞLADI]: {kategori_adi} taranıyor...")
        
        sayfa = 1
        hedef_url = BASE_URL + url_yolu
        gercek_kategori_linki = hedef_url # İlk sayfadaki gerçek yönlendirmeyi tutacak
        
        while True:
            try:
                if sayfa > 1: time.sleep(random.uniform(0.5, 1.5))
                
                req = session.get(hedef_url, timeout=20)
                
                # SİNSİ YÖNLENDİRMEYİ YAKALA: 1. sayfadaysak, sitenin bizi attığı gerçek linki kopyala
                if sayfa == 1:
                    gercek_kategori_linki = req.url
                    if not gercek_kategori_linki.endswith('/'):
                        gercek_kategori_linki += '/'

                if req.status_code == 404: 
                    break

                soup = BeautifulSoup(req.content, 'html.parser')
                film_listesi = soup.select("li.film, div.movie-item, article.film, .movie-list li")
                
                if not film_listesi: 
                    break

                print(f"  📄 Sayfa {sayfa} taranıyor... (Sitede bulunan film: {len(film_listesi)})")
                
                for li in film_listesi:
                    baslik_elem = li.select_one("span.film-title, h2.title, a.title")
                    ham_baslik = baslik_elem.text.strip() if baslik_elem else ""
                    if not ham_baslik: continue
                    baslik = baslik_temizle(ham_baslik)
                    
                    if baslik in mevcut_basliklar:
                        continue 

                    link_elem = li.select_one("a")
                    film_url = link_elem.get("href") if link_elem else ""
                    if not film_url.startswith("http"): film_url = BASE_URL + film_url
                    
                    img = li.select_one("img")
                    afis = img.get("data-src") or img.get("src") or "" if img else ""
                    
                    detay = extract_movie_data(film_url)
                    
                    if detay["iframe"]:
                        print(f"    ✅ Arşive Eklendi: {baslik}")
                        veritabani["filmler"].append({
                            "id": len(veritabani["filmler"]) + 1,
                            "baslik": baslik,
                            "kategori": kategori_adi,
                            "afis": afis,
                            "aciklama": detay["aciklama"],
                            "iframe": detay["iframe"]
                        })
                        mevcut_basliklar.append(baslik)
                        kategori_yeni_film_sayisi += 1
                        genel_toplam_yeni_film += 1
                    else:
                        # Eğer her şeye rağmen oynatıcı yoksa, bize bildirsin!
                        print(f"    ❌ Oynatıcı Bulunamadı, Atlandı: {baslik}")
                        
                # SAYFA DEĞİŞTİRME MOTORU (Gerçek link üzerinden)
                sayfa += 1
                
                next_tag = soup.find('a', class_='next') or soup.select_one('.pagination a.next, a.next-page, a.ileri, a.sonraki')
                if next_tag and next_tag.get('href') and len(next_tag.get('href')) > 5:
                    next_url = next_tag.get('href')
                    hedef_url = next_url if next_url.startswith('http') else (BASE_URL + next_url if next_url.startswith('/') else BASE_URL + "/" + next_url)
                else:
                    # Gerçek yakalanmış link üzerinden tahmin yap!
                    olasi_linkler = [
                        gercek_kategori_linki + f"page/{sayfa}/",
                        gercek_kategori_linki + f"sayfa/{sayfa}/",
                        gercek_kategori_linki + f"sayfa-{sayfa}/"
                    ]
                    sayfa_bulundu = False
                    for link in olasi_linkler:
                        req_test = session.get(link, timeout=15)
                        if req_test.status_code == 200 and BeautifulSoup(req_test.content, 'html.parser').select("li.film, div.movie-item, article.film"):
                            hedef_url = link
                            sayfa_bulundu = True
                            break
                    if not sayfa_bulundu:
                        break

            except Exception as e:
                print(f"  [!] Hata: {e}")
                break
                
        print(f"✅ {kategori_adi} bitti! Toplam {kategori_yeni_film_sayisi} yeni film çekildi.")

    # ==========================================
    # 📊 BİTİŞ VE RAPORLAMA EKRANI
    # ==========================================
    toplam_arsiv_sayisi = len(veritabani["filmler"])
    
    print("\n" + "="*50)
    print("🏁 TARAMA İŞLEMİ SONA ERDİ")
    print(f"🌟 Bu Turda Eklenen Yeni Film: {genel_toplam_yeni_film}")
    print(f"📚 Veritabanındaki Toplam Film: {toplam_arsiv_sayisi}")
    print("="*50)

    if genel_toplam_yeni_film > 0:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(veritabani, f, ensure_ascii=False, indent=4)
        
        tg_mesaj = f"🎬 <b>İnadına TV Bot Raporu</b>\n\n✅ <b>Tarama Tamamlandı!</b>\n🔥 <b>Eklenen Yeni Film:</b> {genel_toplam_yeni_film}\n📚 <b>Arşivdeki Toplam Film:</b> {toplam_arsiv_sayisi}\n\nVercel siteniz otomatik olarak güncellendi! 🚀"
        telegram_mesaj_gonder(tg_mesaj)
    else:
        tg_mesaj = f"🎬 <b>İnadına TV Bot Raporu</b>\n\nℹ️ <b>Sistem Zaten Güncel!</b>\nSitede çekilecek yeni film kalmadı.\n📚 <b>Arşivdeki Toplam Film:</b> {toplam_arsiv_sayisi}"
        telegram_mesaj_gonder(tg_mesaj)

if __name__ == "__main__":
    bot_calistir()
