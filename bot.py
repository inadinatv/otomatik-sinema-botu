import json
import os
import re
import base64
import codecs
from bs4 import BeautifulSoup
from curl_cffi import requests

BASE_URL = "https://www.fullhdfilmizlesene.life"
DB_FILE = "veritabani.json"

# HATANIN KAYNAĞI DÜZELTİLDİ: Sizin ilk verdiğiniz orijinal ve KUSURSUZ linkler geri getirildi.
KATEGORILER = {
    "En Çok İzlenen Filmler": "/en-cok-izlenen-filmler-izle-hd/",
    "IMDB Puanı Yüksek Filmler": "/filmizle/imdb-puani-yuksek-filmler-izle-1/",
    "Aile Filmleri": "/filmizle/aile-filmleri-hdf-izle/",
    "Aksiyon Filmleri": "/filmizle/aksiyon-filmleri-hdf-izle/",
    "Animasyon Filmleri": "/filmizle/animasyon-filmleri-fhd-izle/",
    "Belgeseller": "/filmizle/belgesel-filmleri-izle/",
    "Bilim Kurgu Filmleri": "/filmizle/bilim-kurgu-filmleri-izle-2/",
    "Blu Ray Filmler": "/filmizle/bluray-filmler-izle/",
    "Çizgi Filmler": "/filmizle/cizgi-filmler-fhd-izle/",
    "Dram Filmleri": "/filmizle/dram-filmleri-hd-izle/",
    "Fantastik Filmler": "/filmizle/fantastik-filmler-hd-izle/",
    "Gerilim Filmleri": "/filmizle/gerilim-filmleri-fhd-izle/",
    "Gizem Filmleri": "/filmizle/gizem-filmleri-hd-izle/",
    "Hint Filmleri": "/filmizle/hint-filmleri-fhd-izle/",
    "Komedi Filmleri": "/filmizle/komedi-filmleri-fhd-izle/",
    "Korku Filmleri": "/filmizle/korku-filmleri-izle-3/",
    "Macera Filmleri": "/filmizle/macera-filmleri-fhd-izle/",
    "Müzikal Filmler": "/filmizle/muzikal-filmler-izle/",
    "Polisiye Filmleri": "/filmizle/polisiye-filmleri-izle/",
    "Psikolojik Filmler": "/filmizle/psikolojik-filmler-izle/",
    "Romantik Filmler": "/filmizle/romantik-filmler-fhd-izle/",
    "Savaş Filmleri": "/filmizle/savas-filmleri-fhd-izle/",
    "Suç Filmleri": "/filmizle/suc-filmleri-izle/",
    "Tarih Filmleri": "/filmizle/tarih-filmleri-fhd-izle/",
    "Western Filmler": "/filmizle/western-filmler-hd-izle-3/",
    "Yerli Filmler": "/filmizle/yerli-filmler-hd-izle/"
}

PROXY = {"http": "socks5h://127.0.0.1:40000", "https": "socks5h://127.0.0.1:40000"}
session = requests.Session(impersonate="chrome120", proxies=PROXY)
session.headers.update({
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": "https://www.google.com/"
})

def decode_iframe(s):
    if not isinstance(s, str) or len(s) < 10: return None
    s = s.strip()
    if s.startswith("//"): return "https:" + s
    if s.startswith("http"): return s
    s_pad = s + '=' * (-len(s) % 4)
    for method in ['rot13_b64', 'b64']:
        try:
            dec = base64.b64decode(codecs.encode(s_pad, 'rot_13')).decode('utf-8') if method == 'rot13_b64' else base64.b64decode(s_pad).decode('utf-8')
            if "http" in dec and ("vod" in dec or "embed" in dec or "player" in dec): return dec.replace("\\/", "/")
        except: pass
    return None

def extract_movie_data(film_url):
    try:
        req = session.get(film_url, timeout=15)
        soup = BeautifulSoup(req.text, 'html.parser')
        
        aciklama = ""
        
        # 1. YÖNTEM: Eksiksiz Sınıf Taraması (.film-content geri eklendi)
        ozet_div = soup.select_one(".ozet, .summary, .film-content, .film-ozeti, div[itemprop='description'], p[itemprop='description']")
        if ozet_div: 
            aciklama = ozet_div.text.strip()
            
        # 2. YÖNTEM: Div yoksa yazıyı direkt sayfa paragraflarının (p etiketlerinin) içinden söküp al!
        if not aciklama or len(aciklama) < 10:
            paragraphs = soup.select('article p, .post-content p')
            if paragraphs:
                aciklama = " ".join([p.text.strip() for p in paragraphs if len(p.text.strip()) > 15])
                
        # 3. YÖNTEM: Meta Etiketi (En son çare)
        if not aciklama or len(aciklama) < 10:
            meta_desc = soup.select_one('meta[name="description"]')
            if meta_desc: 
                aciklama = meta_desc.get("content", "").strip()
                
        if not aciklama: 
            aciklama = "Bu film için açıklama bulunamadı."

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
            for tag in soup.find_all(['iframe', 'a', 'div']):
                val = tag.get('src') or tag.get('data-src') or tag.get('data-url')
                if val and ('vod' in val or 'embed' in val or 'rapidvid' in val):
                    iframe_linki = "https:" + val if val.startswith('//') else val
                    break

        return {"aciklama": aciklama, "iframe": iframe_linki}
    except:
        return {"aciklama": "Veri alınamadı.", "iframe": None}

def bot_calistir():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f: veritabani = json.load(f)
    else: veritabani = {"kategoriler": list(KATEGORILER.keys()), "filmler": []}

    mevcut_basliklar = [film["baslik"] for film in veritabani.get("filmler", [])]
    yeni_film_eklendi = False
    
    for kategori_adi, url_yolu in KATEGORILER.items():
        print(f"\n>> Taraniyor: {kategori_adi}")
        hedef_url = BASE_URL + url_yolu
        
        try:
            req = session.get(hedef_url, timeout=20)
            if req.status_code != 200: 
                print(f"  [!] HTTP Hatası: {req.status_code}")
                continue

            soup = BeautifulSoup(req.content, 'html.parser')
            film_listesi = soup.select("li.film, div.movie-item, article.film, .movie-list li")
            
            if not film_listesi: 
                print("  [!] Bu kategoride film listesi bulunamadı.")
                continue

            for li in film_listesi:
                baslik_elem = li.select_one("span.film-title, h2.title, a.title")
                baslik = baslik_elem.text.strip() if baslik_elem else ""
                
                # Zaten olan filmi atla
                if not baslik or baslik in mevcut_basliklar: continue 

                link_elem = li.select_one("a")
                film_url = link_elem.get("href") if link_elem else ""
                if not film_url.startswith("http"): film_url = BASE_URL + film_url
                
                img = li.select_one("img")
                afis = img.get("data-src") or img.get("src") or "" if img else ""
                
                print(f"  🎬 Yeni Film: {baslik}")
                detay = extract_movie_data(film_url)
                
                if detay["iframe"]:
                    veritabani["filmler"].insert(0, {
                        "id": len(veritabani["filmler"]) + 1,
                        "baslik": baslik,
                        "kategori": kategori_adi,
                        "afis": afis,
                        "aciklama": detay["aciklama"], # Artık boş dönmeyecek!
                        "iframe": detay["iframe"]
                    })
                    mevcut_basliklar.append(baslik)
                    yeni_film_eklendi = True
        except Exception as e:
            print(f"  [!] Hata: {e}")

    if yeni_film_eklendi:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(veritabani, f, ensure_ascii=False, indent=4)
        print("\n🎉 Veritabanı başarıyla güncellendi!")
    else:
        print("\nYeni film bulunamadı, sistem güncel.")

if __name__ == "__main__":
    bot_calistir()
