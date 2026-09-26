# İnadına TV — Güncel Sinema Arşivi

Bu proje **statik sinema arayüzü** ve ayrı çalışan **katalog güncelleme botu** olarak iki parçalıdır.

- `index.html`: Cloudflare Pages veya Vercel üzerinde yayınlanır.
- `veritabani.json`: Yayında gösterilen film kataloğudur.
- `bot.py`: Güncel film kartlarını ve sayfanın yayımladığı embed metadata'sını okuyarak JSON'u günceller.
- `vercel.json`, `_headers`, `_redirects`: İki platforma uygun statik yayın ayarlarıdır.

> Statik hosting Python botunu sürekli çalıştırmaz. Bu nedenle Pages/Vercel film sitesini servis eder; bot ayrı bir bilgisayarda, GitHub Actions'ta veya manuel olarak çalıştırılıp güncellenen `veritabani.json` yeniden deploy edilir.

## Yerel çalıştırma

```bash
python3 -m pip install -r requirements.txt
python3 -m http.server 8080
# http://localhost:8080
```

Katalog güncellemek için:

```bash
export TELEGRAM_BOT_TOKEN='...'
export TELEGRAM_CHAT_ID='...'
python3 bot.py
```

Telegram değişkenleri verilmezse katalog güncellenir, bildirim gönderilmez. Daha önce token'ı kaynak kodunda kullandıysanız **BotFather üzerinden token'ı yenileyin**.

## Cloudflare Pages

Cloudflare Pages için proje kökü doğrudan bu klasördür:

| Ayar | Değer |
|---|---|
| Framework preset | None / düz statik site |
| Build command | Boş bırakılabilir |
| Build output directory | `/` veya proje kökü |
| Root directory | `/` |

GitHub deposunu bağlayıp deploy ettiğinizde `index.html`, `veritabani.json`, `_headers` ve `_redirects` doğrudan yayınlanır.

## Vercel

Vercel panelinde GitHub reposunu içe aktarın:

| Ayar | Değer |
|---|---|
| Framework preset | Other |
| Build command | Boş bırakılabilir |
| Output directory | `.` |
| Install command | Boş bırakılabilir |

Depodaki `vercel.json` güvenlik başlıklarını ve JSON için cache davranışını ayarlar. CLI ile:

```bash
npm i -g vercel
vercel --prod
```

## Güncel veri yayınlama seçenekleri

1. **Manuel ve hafif:** `python3 bot.py` çalıştırılır, değişen `veritabani.json` commit edilip Pages/Vercel yeniden deploy edilir.
2. **Otomatik:** Bot, GitHub Actions gibi zamanlanmış bir görevde çalıştırılır; yalnızca değişen `veritabani.json` commit edilir. Vercel veya Pages Git entegrasyonu yeni commit'i otomatik yayınlar.

Vercel'in statik siteyi servis etmesi ücretsiz ve basittir; botu sürekli Vercel Function içinde çalıştırmak uygun değildir çünkü dosya sistemi kalıcı değildir ve uzun taramalar serverless çalışma sınırlarına takılabilir.

## Ortam değişkenleri

```bash
FILM_SITE_URL=https://www.fullhdfilmizlesene.now
DB_FILE=veritabani.json
REQUEST_DELAY=1.0
MAX_PAGES_PER_CATEGORY=1
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Gerçek token'ları `.env` veya git deposuna koymayın. `.env.example` yalnızca şablondur.

## Teknik not

Site iframe'i ilk HTML'e doğrudan koymuyor. Film sayfasındaki `scx` nesnesinin `sx.p` / `sx.t` değerleri ROT13 + Base64 ile çözülüyor ve sayfanın kendi embed URL'si `kaynaklar` alanına yazılıyor. Bot CAPTCHA, Cloudflare veya erişim kontrolü aşmaya çalışmaz; medya akışını indirmez.

## Test

```bash
python3 -m pytest -q
```
