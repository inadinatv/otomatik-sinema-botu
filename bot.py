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
        hedef_url = BASE_URL + url_yolu
        
        while True:
            try:
                req = session.get(hedef_url, timeout=20)
                if req.status_code == 404: 
                    print(f"  🏁 Sayfa {sayfa} boş çıktı. Bu kategorinin tüm filmleri başarıyla çekildi!")
                    break

                soup = BeautifulSoup(req.content, 'html.parser')
                film_listesi = soup.select("li.film, div.movie-item, article.film, .movie-list li")
                
                if not film_listesi: 
                    print("  🏁 Bu sayfada listelenecek film kalmadı, kategori tamamlandı.")
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
                        
                # --- AKILLI BUTON AVCISI (DYNAMIC PAGINATION) ---
                sayfa += 1
                next_url = None
                
                # Sitenin en altındaki "Sonraki Sayfa" tuşunu bizzat arar (Sınıf isimleriyle)
                next_tag = soup.find('a', rel='next') or soup.select_one('.pagination a.next, .sayfalama a.next, .nav-links a.next, a.next-page, a.ileri, a.sonraki, a.nextpostslink')
                
                # Eğer özel bir sınıf yoksa, rakamlara bakarak bulur (Örn: "2", "3")
                if not next_tag:
                    for a in soup.select('.pagination a, .sayfalama a, .pages a, .nav-links a'):
                        if a.text.strip() == str(sayfa) or "Sonraki" in a.text or ">" in a.text:
                            next_tag = a
                            break
                            
                # Eğer butonu başarıyla bulduysa o gizli linki alıp döngüye devam eder
                if next_tag and next_tag.get('href') and len(next_tag.get('href')) > 5:
                    next_url = next_tag.get('href')
                    if not next_url.startswith('http'):
                        next_url = BASE_URL + next_url if next_url.startswith('/') else BASE_URL + "/" + next_url
                    
                    hedef_url = next_url
                    print(f"  🔗 [Akıllı Sistem] Sonraki sayfa linki bulundu, yola devam ediliyor...")
                    continue
                    
                # Eğer sitede buton okunamazsa ZORLA TAHMİN ET:
                olasi_linkler = [
                    BASE_URL + url_yolu + f"sayfa-{sayfa}/",
                    BASE_URL + url_yolu + f"page/{sayfa}/",
                    BASE_URL + url_yolu + f"sayfa/{sayfa}/",
                    BASE_URL + url_yolu + f"{sayfa}/",
                    BASE_URL + url_yolu.rstrip('/') + f"-sayfa-{sayfa}/",
                    BASE_URL + url_yolu + f"?page={sayfa}"
                ]
                
                sayfa_bulundu = False
                for link in olasi_linkler:
                    req_test = session.get(link, timeout=15)
                    if req_test.status_code == 200:
                        test_soup = BeautifulSoup(req_test.content, 'html.parser')
                        if test_soup.select("li.film, div.movie-item, article.film, .movie-list li"):
                            hedef_url = link
                            sayfa_bulundu = True
                            print(f"  🔗 [Tahmin Sistemi] Sonraki sayfa adresi kırıldı, yola devam ediliyor...")
                            break
                            
                if not sayfa_bulundu:
                    print(f"  🏁 Bu kategoride başka sayfa kalmadı veya bitti. Sıradaki kategoriye geçiliyor.")
                    break

            except Exception as e:
                print(f"  [!] Beklenmeyen hata oluştu, diğer kategoriye geçiliyor: {e}")
                break

    if yeni_film_eklendi:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(veritabani, f, ensure_ascii=False, indent=4)
        print("\n🎉 MÜJDE! Devasa arşiv başarıyla veritabanına kaydedildi.")
    else:
        print("\n✅ Sistem tamamen güncel, sitedeki tüm arşiv zaten bizde var.")

if __name__ == "__main__":
    bot_calistir()
