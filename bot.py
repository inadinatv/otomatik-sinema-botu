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
        print(f"\n>> 📂 Kategori: {kategori_adi} | DEVASA ARŞİV TARAMASI BAŞLADI")
        
        sayfa = 1
        while True:
            # URL SAYFALAMA MANTIĞI - 3 Farklı Varyasyon Denenir
            if sayfa == 1:
                hedef_url = BASE_URL + url_yolu
            else:
                hedef_url = BASE_URL + url_yolu + f"page/{sayfa}/"
                
            try:
                req = session.get(hedef_url, timeout=20)
                
                # Eğer /page/2/ çalışmazsa, /sayfa-2/ formatını dene
                if req.status_code == 404 and sayfa > 1:
                    hedef_url = BASE_URL + url_yolu + f"sayfa-{sayfa}/"
                    req = session.get(hedef_url, timeout=20)
                    
                # Eğer o da çalışmazsa /sayfa/2/ formatını dene
                if req.status_code == 404 and sayfa > 1:
                    hedef_url = BASE_URL + url_yolu + f"sayfa/{sayfa}/"
                    req = session.get(hedef_url, timeout=20)

                # Hiçbiri çalışmazsa demek ki sitenin o kategorisinin gerçekten sonuna gelmişizdir.
                if req.status_code == 404: 
                    print(f"  🏁 Sayfa {sayfa} bulunamadı. Bu kategorideki TÜM FİLMLER çekildi!")
                    break

                soup = BeautifulSoup(req.content, 'html.parser')
                film_listesi = soup.select("li.film, div.movie-item, article.film, .movie-list li")
                
                if not film_listesi: 
                    print("  🏁 Bu sayfada film kalmadı, kategori tamamlandı.")
                    break

                print(f"\n  ================ SAYFA {sayfa} İÇİNE GİRİLDİ ================")
                for li in film_listesi:
                    baslik_elem = li.select_one("span.film-title, h2.title, a.title")
                    baslik = baslik_elem.text.strip() if baslik_elem else ""
                    
                    if not baslik: continue
                    
                    if baslik in mevcut_basliklar:
                        print(f"  ⏩ Atlandı (Daha önce kaydedilmiş): {baslik}")
                        continue 

                    link_elem = li.select_one("a")
                    film_url = link_elem.get("href") if link_elem else ""
                    if not film_url.startswith("http"): film_url = BASE_URL + film_url
                    
                    img = li.select_one("img")
                    afis = img.get("data-src") or img.get("src") or "" if img else ""
                    
                    print(f"  📥 ARŞİVE EKLENİYOR: {baslik}")
                    detay = extract_movie_data(film_url)
                    
                    if detay["iframe"]:
                        veritabani["filmler"].append({
                            "id": len(veritabani["filmler"]) + 1,
                            "baslik": baslik,
                            "kategori": kategori_adi,
                            "afis": afis,
                            "aciklama": detay["aciklama"],
                            "iframe": detay["iframe"]
                        })
                        mevcut_basliklar.append(baslik)
                        yeni_film_eklendi = True
                        
            except Exception as e:
                print(f"  [!] Hata oluştu, diğer sayfaya geçiliyor: {e}")
                break
            
            # Sayfadaki 20 film bitti, şimdi BİR SONRAKİ SAYFAYA GEÇ (Sonsuz Döngü)
            sayfa += 1 

    if yeni_film_eklendi:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(veritabani, f, ensure_ascii=False, indent=4)
        print("\n🎉 MÜJDE! Devasa arşiv başarıyla veritabanına kaydedildi.")
    else:
        print("\n✅ Sistem tamamen güncel, sitedeki tüm arşiv zaten bizde var.")

if __name__ == "__main__":
    bot_calistir()
