import json
import os
import re
import base64
import codecs
from bs4 import BeautifulSoup
from curl_cffi import requests

BASE_URL = "https://www.fullhdfilmizlesene.life"
DB_FILE = "veritabani.json"

KATEGORILER = {
    "Aksiyon": "/filmizle/aksiyon-filmleri-hdf-izle/",
    "Bilim Kurgu": "/filmizle/bilim-kurgu-filmleri-izle-2/",
    "Animasyon": "/filmizle/animasyon-filmleri-izle-1/",
    "Korku": "/filmizle/korku-filmleri-izle-1/"
}

# GitHub'a kurduğumuz WARP VPN tünelinin adresini veriyoruz
PROXY = {"http": "socks5h://127.0.0.1:40000", "https": "socks5h://127.0.0.1:40000"}

session = requests.Session(impersonate="chrome120", proxies=PROXY)
session.headers.update({
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
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
        
        ozet_elem = soup.select_one(".ozet, .summary, p[itemprop='description']")
        aciklama = ozet_elem.text.strip() if ozet_elem else "Açıklama bulunamadı."
        
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
    except Exception as e:
        print(f"      [!] Hata: {e}")
        return {"aciklama": "", "iframe": None}

def bot_calistir():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            veritabani = json.load(f)
    else:
        veritabani = {"kategoriler": list(KATEGORILER.keys()), "filmler": []}

    mevcut_basliklar = [film["baslik"] for film in veritabani.get("filmler", [])]
    yeni_film_eklendi = False
    
    for kategori_adi, url_yolu in KATEGORILER.items():
        print(f"\n>> Taraniyor: {kategori_adi}")
        try:
            req = session.get(BASE_URL + url_yolu, timeout=20)
            
            # Hata varsa artık bize dürüstçe söyleyecek
            if req.status_code != 200:
                print(f"  [!] Site engelledi. HTTP Hatasi: {req.status_code}")
                continue
                
            if "Just a moment" in req.text or "cf-browser-verification" in req.text:
                print("  [!] Cloudflare engeli VPN'e rağmen aşılamadı!")
                continue

            soup = BeautifulSoup(req.content, 'html.parser')
            film_listesi = soup.select("li.film, div.movie-item, article.film, .movie-list li")
            
            if not film_listesi:
                print("  [!] Bu sayfada film bulunamadı, site linki veya yapısı değişmiş olabilir.")
                continue

            for li in film_listesi[:10]:
                baslik_elem = li.select_one("span.film-title, h2.title, a.title")
                baslik = baslik_elem.text.strip() if baslik_elem else ""
                
                if not baslik or baslik in mevcut_basliklar:
                    continue 

                link_elem = li.select_one("a")
                film_url = link_elem.get("href") if link_elem else ""
                if not film_url.startswith("http"): film_url = BASE_URL + film_url
                
                img = li.select_one("img")
                afis = img.get("data-src") or img.get("src") or "" if img else ""
                
                print(f"  🎬 Yeni Film: {baslik}")
                detay = extract_movie_data(film_url)
                
                if detay["iframe"]:
                    print(f"    ✅ İframe bulundu!")
                    veritabani["filmler"].insert(0, {
                        "id": len(veritabani["filmler"]) + 1,
                        "baslik": baslik,
                        "kategori": kategori_adi,
                        "afis": afis,
                        "aciklama": detay["aciklama"],
                        "iframe": detay["iframe"]
                    })
                    mevcut_basliklar.append(baslik)
                    yeni_film_eklendi = True
                else:
                    print(f"    ❌ İframe (oynatıcı) yok.")
        except Exception as e:
            print(f"  [!] Kategori Hatasi: {e}")

    if yeni_film_eklendi:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(veritabani, f, ensure_ascii=False, indent=4)
        print("\n🎉 Veritabani.json başarıyla güncellendi!")
    else:
        print("\nYeni film bulunamadı, sistem güncel.")

if __name__ == "__main__":
    bot_calistir()
