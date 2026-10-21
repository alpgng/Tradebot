# Tradebot Web Panel

Mevcut `TradeCode.py` olduğu gibi duruyor; bu yapı onun yanında, ayrı bir paket (`tradebot/`) olarak çalışır.
Birden çok botu, stratejilerini ve parametrelerini sunucuda tarayıcıdan yönetmenizi sağlar.

## Kurulum

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # ADMIN_PASSWORD, SECRET_KEY ve gerekiyorsa API anahtarlarını doldurun
python run.py             # http://127.0.0.1:8000
```

Sunucuda dışarı açmak için `python run.py --host 0.0.0.0` yerine panelin önüne HTTPS'li bir reverse proxy
(nginx/Caddy) koymanız ve `.env` içinde `SESSION_HTTPS_ONLY=true` yapmanız önerilir.
Botlar API süreci içinde thread olarak çalıştığı için uvicorn'u tek worker ile çalıştırın.

## Modlar

| Mod | Veri | Emirler |
|---|---|---|
| `dry` | Gerçek Binance verisi (anahtarsız) | Simüle edilir, sadece veritabanına yazılır |
| `testnet` | Binance Spot Testnet | Testnet hesabına gerçekten gönderilir (sahte bakiye) |
| `live` | Gerçek | Gerçek hesap. `ALLOW_LIVE_TRADING=true` olmadan başlatılamaz |

## Panel

- Bot listesi: durum, açık pozisyon, son çalışma, son hata
- Başlat / durdur / düzenle / sil, "pozisyon kaydını sıfırla"
- Strateji seçimi ve şemadan otomatik oluşan parametre formu. Çalışan botun parametreleri
  durdurmadan değiştirilebilir, bir sonraki turda devreye girer (parite, mod ve strateji için önce durdurmak gerekir).
- Loglar ve emir geçmişi (tüm botlar veya seçili bot)

## Stratejiler

`tradebot/strategies/` altında, her biri parametre şemasıyla birlikte:

- **combined**: Orijinal bottaki Golden Cross + Bollinger + RSI + MACD, oylama ile (`min_votes`).
- **golden_cross**: Sadece SMA kesişim anında al/sat.
- **rsi**: Aşırı satımda al, aşırı alımda sat.
- **bollinger**: Alt bant altında al, üst bant üstünde sat.

Yeni strateji eklemek için `Strategy` sınıfından türetip `params` listesini ve `evaluate()` metodunu yazın,
sonra `tradebot/strategies/__init__.py` içindeki `STRATEGIES`'e ekleyin. Panel formu şemadan otomatik oluşur.

## Eski koda göre düzeltilen hatalar

- Bollinger alt/üst bantları ters atanmıştı (`BB_High = BBL`, `BB_Low = BBU`).
- Golden Cross, SMA50 > SMA200 olduğu sürece her saat alım sinyali veriyordu; artık sadece kesişim mumunda.
- MACD de kesişim değil durum kontrol ediyordu, her turda al ya da sat sinyali çıkıyordu.
- Aynı turda birden çok alım ve satım emri gönderilebiliyordu; artık tur başına tek karar.
- Pozisyon takibi yoktu; artık pozisyon yokken satış, pozisyon varken tekrar alım yapılmaz.
- Henüz kapanmamış son mum kullanılıyordu; artık sadece kapanmış mumlar değerlendirilir ve her mum bir kez işlenir.
- API anahtarları koddaydı; artık `.env` üzerinden okunur.

## Bilinen sınırlamalar

- Emir miktarı Binance'in `LOT_SIZE`/`MIN_NOTIONAL` kurallarına göre yuvarlanmıyor; uygun bir miktar girin.
- Canlı modda alım komisyonu baz varlıktan kesilirse, satışta tam miktar bakiyede olmayabilir.

## Testler

```bash
python -m pytest
```
