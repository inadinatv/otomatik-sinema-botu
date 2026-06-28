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

def gecerli_oynatici_mi(url):
    if not url or len(url) < 10: return False
    url_low = url.lower()
    yasakli_uzantilar = [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".css", ".js"]
    if any(uzanti in url_low for uzanti in yasakli_uzantilar): return False
    yasakli_siteler = ["youtube.com", "youtu.be", "vimeo", "fragman", "google.com", "ads", "imdb.com"]
    if any(yasak in url_low for yasak in yasakli_siteler): return False
    gecerli_sunucular = ["trstx", "vidmoly", "rapidvid", "embed", "player", "vod", "play", "video", "iframe", "proton", "fast"]
    if any(gecerli in url_low for gecerli in gecerli_sunucular): return True
    return False

def decode_iframe(s):
    if not isinstance(s, str) or len(s) < 10: return None
    s = s.strip()
    s_pad = s + '=' * (-len(s) % 4)
    for method in ['rot13_b64', 'b64']:
        try:
            dec = base64.b64decode(codecs.encode(s_pad, 'rot_13')).decode('utf-8') if method == 'rot13_b64' else base64.b64decode(s_pad).decode('utf-8')
            if "http" in dec: 
                temiz_link = dec.replace("\\/", "/")
                if gecerli_oynatici_mi(temiz_link): return temiz_link
        except: pass
    return None

def extract_movie_data(film_url):
    try:
        req = session.get(film_url, timeout=15)
        soup = BeautifulSoup(req.text, 'html.parser')
        
        sayfa_metni = soup.text.lower()
        yasakli_durumlar = ["yapım aşamasında", "henüz sitemize eklenmemiştir", "yakında sinemalarda", "telif hakkı nedeniyle kaldırılmıştır"]
        for durum in yasakli_durumlar:
            if durum in sayfa_metni: return {"aciklama": "", "iframe": None, "hata": "Yapım Aşamasında / Telif Yemiş"}

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
        scx_match = re.search(r'(?:scx|data)\s*=\s*(\{.*?\});', req.text)
        if scx_match:
            encoded_strings = re.findall(r"'(.*?)'", str(json.loads(scx_match.group(1))))
            for code in encoded_strings:
                dec = decode_iframe(code)
                if dec: 
                    iframe_linki = dec
                    break

        if not iframe_linki:
            for tag in soup.find_all(['iframe', 'embed']):
                val = tag.get('src') or tag.get('data-src') or tag.get('data-lazy-src')
                if val and val.startswith('//'): val = "https:" + val
                if gecerli_oynatici_mi(val):
                    iframe_linki = val
                    break
                    
        if not iframe_linki:
            embed_match = re.search(r'[\"\'](https?://[^\"\']+(?:embed|v|player|video|play|rapidvid|vidmoly)[^\"\']+)[\"\']', req.text)
            if embed_match:
                link = embed_match.group(1).replace("\\/", "/")
                if gecerli_oynatici_mi(link): iframe_linki = link

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
    print("🚀 İNADINA TV - OYNATICI DOĞRULAMALI DERİN KAZICI")
    print("="*50)
    
    for kategori_adi, url_yolu in KATEGORILER.items():
        kategori_yeni_film_sayisi = 0
        print(f"\n📁 [KATEGORİ BAŞLADI]: {kategori_adi} taranıyor...")
        
        sayfa = 1
        hedef_url = BASE_URL + url_yolu
        gercek_kategori_linki = hedef_url
        
        while True:
            try:
                if sayfa > 1: time.sleep(random.uniform(0.5, 1.5))
                req = session.get(hedef_url, timeout=20)
                
                if sayfa == 1:
                    gercek_kategori_linki = req.url
                    if not gercek_kategori_linki.endswith('/'): gercek_kategori_linki += '/'

                if req.status_code == 404: break

                soup = BeautifulSoup(req.content, 'html.parser')
                film_listesi = soup.select("li.film, div.movie-item, article.film, .movie-list li")
                if not film_listesi: break

                print(f"  📄 Sayfa {sayfa} taranıyor... (İncelenen film: {len(film_listesi)})")
                
                for li in film_listesi:
                    baslik_elem = li.select_one("span.film-title, h2.title, a.title")
                    ham_baslik = baslik_elem.text.strip() if baslik_elem else ""
                    if not ham_baslik: continue
                    baslik = baslik_temizle(ham_baslik)
                    
                    if baslik in mevcut_basliklar: continue 

                    link_elem = li.select_one("a")
                    film_url = link_elem.get("href") if link_elem else ""
                    if not film_url.startswith("http"): film_url = BASE_URL + film_url
                    
                    img = li.select_one("img")
                    afis = img.get("data-src") or img.get("src") or "" if img else ""
                    
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
                            "sayfa": sayfa # YENİ YZ SIRALAMA İÇİN EKLENDİ!
                        })
                        mevcut_basliklar.append(baslik)
                        kategori_yeni_film_sayisi += 1
                        genel_toplam_yeni_film += 1
                    else:
                        print(f"    ❌ Reddedildi ({detay['hata']}): {baslik}")
                        
                sayfa += 1
                next_tag = soup.find('a', class_='next') or soup.select_one('.pagination a.next, a.next-page, a.ileri, a.sonraki')
                if next_tag and next_tag.get('href') and len(next_tag.get('href')) > 5:
                    next_url = next_tag.get('href')
                    hedef_url = next_url if next_url.startswith('http') else (BASE_URL + next_url if next_url.startswith('/') else BASE_URL + "/" + next_url)
                else:
                    olasi_linkler = [gercek_kategori_linki + f"page/{sayfa}/", gercek_kategori_linki + f"sayfa/{sayfa}/", gercek_kategori_linki + f"sayfa-{sayfa}/"]
                    sayfa_bulundu = False
                    for link in olasi_linkler:
                        req_test = session.get(link, timeout=15)
                        if req_test.status_code == 200 and BeautifulSoup(req_test.content, 'html.parser').select("li.film, div.movie-item, article.film"):
                            hedef_url = link
                            sayfa_bulundu = True
                            break
                    if not sayfa_bulundu: break

            except Exception as e:
                print(f"  [!] Hata: {e}")
                break
                
        print(f"✅ {kategori_adi} bitti! Toplam {kategori_yeni_film_sayisi} gerçek video çekildi.")

    if genel_toplam_yeni_film > 0:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(veritabani, f, ensure_ascii=False, indent=4)
        tg_mesaj = f"🎬 <b>İnadına TV Bot Raporu</b>\n\n✅ <b>Tarama Tamamlandı!</b>\n🔥 <b>Eklenen Gerçek Videolu Film:</b> {genel_toplam_yeni_film}\n📚 <b>Arşivdeki Toplam Film:</b> {len(veritabani['filmler'])}\n\nVercel siteniz güncellendi! 🚀"
        telegram_mesaj_gonder(tg_mesaj)

if __name__ == "__main__":
    bot_calistir()
