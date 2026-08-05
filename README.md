# İnadına TV Bot

Film izleme sitesi için otomatik film veri çekme botu ve web arayüzü.

## 📁 Dosyalar

- `bot.py` - Film verilerini çeken Python botu
- `index.html` - Modern web arayüzü
- `requirements.txt` - Python bağımlılıkları
- `.env.example` - Ortam değişkenleri şablonu

## 🚀 Kurulum

### 1. Bağımlılıkları Yükle

```bash
pip install -r requirements.txt
```

### 2. Ortam Değişkenlerini Ayarla

Telegram bildirimleri ve Cloudflare bypass için `.env` dosyası oluşturun:

```bash
cp .env.example .env
```

`.env` dosyasını düzenleyin:
```
# Telegram Bildirimleri (Opsiyonel)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# Cloudflare Bypass - FlareSolverr (Önerilen)
# Docker ile FlareSolverr çalıştırın: docker run -d -p 8191:8191 flaresolverr/flaresolverr:latest
FLARESOLVERR_URL=http://localhost:8191

# Alternatif: Manuel Cookie (FlareSolverr yoksa)
# Tarayıcınızdan cf_clearance cookie'sini kopyalayın
CF_COOKIE=your_cf_clearance_cookie_here
```

### 3. Botu Çalıştır

```bash
python bot.py
```

## 🔥 Cloudflare Koruması

Hedef site (`fullhdfilmizlesene.mx`) Cloudflare ile korunmaktadır. Bot'u çalıştırmak için aşağıdaki yöntemlerden birini kullanmalısınız:

### Yöntem 1: FlareSolverr (Önerilen)

1. **Docker ile FlareSolverr kurun:**
   ```bash
   docker run -d -p 8191:8191 flaresolverr/flaresolverr:latest
   ```

2. **`.env` dosyasına ekleyin:**
   ```
   FLARESOLVERR_URL=http://localhost:8191
   ```

### Yöntem 2: Manuel Cookie

1. Tarayıcınızda `https://www.fullhdfilmizlesene.mx` adresini açın
2. Cloudflare doğrulamasını geçin
3. Developer Tools > Application > Cookies bölümünden `cf_clearance` değerini kopyalayın
4. `.env` dosyasına ekleyin:
   ```
   CF_COOKIE=your_cf_clearance_value_here
   ```

### Yöntem 3: Selenium/Playwright

Gerçek tarayıcı otomasyonu kullanarak Cloudflare'i geçebilirsiniz:
```bash
pip install selenium webdriver-manager
# veya
pip install playwright && playwright install chromium
```

## 🎬 Web Arayüzü

`index.html` dosyasını bir web sunucusunda host edin veya yerel olarak açın:

```bash
python -m http.server 8000
```

Tarayıcıda `http://localhost:8000` adresini ziyaret edin.

## ⚙️ Özellikler

- **Otomatik Film Çekme**: 24 farklı kategoride film bilgilerini çeker
- **Iframe Dedektörü**: Gizlenmiş video oynatıcı linklerini bulur (Base64, data-attribute, JS embedded)
- **Cloudflare Bypass**: FlareSolverr entegrasyonu ile güvenlik engellerini aşar
- **Telegram Bildirimleri**: Yeni filmler hakkında bildirim gönderir
- **Modern Web UI**: Responsive, karanlık mod, arama ve sıralama özellikleri
- **Akıllı Retry**: 403 hatalarında otomatik tekrar dener

## 📝 Notlar

- Bot, hedef sitenin kullanım koşullarına uygun şekilde kullanılmalıdır
- API anahtarlarınızı asla paylaşmayın
- Veritabanı dosyası (`veritabani.json`) otomatik oluşturulur
- Cloudflare nedeniyle bot sadece FlareSolverr veya geçerli cookie ile çalışır

## 🛡️ Güvenlik

- Telegram token'ları ortam değişkenlerinden okunur
- Hassas bilgiler `.gitignore` ile korunur
- Hata yönetimi ve loglama iyileştirilmiştir
- IP ban önleme için istekler arası bekleme süreleri vardır

## 🐛 Sorun Giderme

### "403 Forbidden" hatası alıyorum
- FlareSolverr'ın çalıştığından emin olun (`docker ps`)
- Veya manuel cookie yöntemini kullanın

### "Oynatıcı Bulunamadı" hatası
- Site HTML yapısını değiştirmiş olabilir
- Bot'un en güncel sürümünü kullandığınızdan emin olun

### Bot çok yavaş çalışıyor
- Bu normaldir - IP ban önleme için istekler arası 2-3 saniye bekler
