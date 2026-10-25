# MyWeTransfer

> Flask ile geliştirilmiş, kullanıcı hesabı olmadan veya oturum açarak dosya paylaşımı yapılabilen bir WeTransfer esintili demo uygulaması.

[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.1-000000?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

## Neler sunuyor?

- Bir veya birden fazla dosyayı tek bir ZIP paketi olarak paylaşma
- Tahmin edilmesi zor, rastgele oluşturulmuş indirme bağlantıları
- Hesap oluşturma, oturum yönetimi ve kullanıcı dosya yükleme alanı
- Yönetici rolü ile kullanıcı rolü yönetimi
- İsteğe bağlı SMTP e-posta bildirimleri
- SQLite ile hızlı yerel başlangıç; PostgreSQL bağlantı dizesi desteği

## Güvenlik yaklaşımı

Bu proje bir demo/portföy uygulamasıdır; yine de temel güvenlik ilkelerini uygular:

- Gizli yapılandırma `.env` içinde tutulur; Git tarafından izlenmez.
- İndirme dosyaları kullanıcı adıyla değil, rastgele oluşturulan sunucu adlarıyla saklanır.
- Parolalar Werkzeug ile hash’lenir; düz metin parola kabul edilmez.
- Yönetici işlemleri rol doğrulaması, POST işlemleri ise CSRF doğrulaması gerektirir.
- Üretimde `SECRET_KEY` zorunludur; debug modu varsayılan olarak kapalıdır.
- Uygulama kart numarası, CVV veya ödeme verisi işlemez. Gerçek abonelik için PCI-DSS uyumlu bir ödeme sağlayıcısı (ör. Stripe/Iyzico) kullanılmalıdır.

## Hızlı başlangıç

```bash
git clone https://github.com/esrayamann/mywetransfer.git
cd mywetransfer

python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp env.example .env
# .env içindeki SECRET_KEY değerini güçlü ve benzersiz bir değerle güncelleyin.

flask --app app init-db
flask --app app run --debug
```

Uygulama varsayılan olarak `http://127.0.0.1:5000` adresinde çalışır.

## Testler

```bash
python -m unittest discover -s tests -v
```

Test paketi; CSRF doğrulamasını, yetkisiz yönetici paneli erişimini ve rastgele adlandırılmış aktarım dosyasının indirme akışını kontrol eder.

## Yapılandırma

`.env` dosyanızı yalnızca yerelde veya güvenli bir dağıtım gizli-değer yöneticisinde saklayın.

| Değişken | Amaç | Varsayılan |
| --- | --- | --- |
| `DATABASE_URL` | SQLite veya PostgreSQL bağlantısı | `sqlite:///app.db` |
| `SECRET_KEY` | Oturumları imzalamak için gizli anahtar | Üretimde zorunlu |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | SMTP bildirimleri | Boşsa e-posta gönderilmez |
| `MAX_UPLOAD_MB` | Aktarım başına toplam boyut limiti | `100` |
| `MAX_FILES_PER_TRANSFER` | Aktarım başına dosya adedi limiti | `25` |
| `FLASK_ENV` | Ortam modu | geliştirme |
| `FLASK_DEBUG` | Flask debug modu | `false` |

Güvenli bir anahtar üretmek için:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Üretime alma

Önce yapılandırmayı güvenli biçimde sağlayın, ardından tabloları bir kez oluşturun:

```bash
flask --app app init-db
gunicorn --bind 0.0.0.0:8000 app:app
```

Üretimde HTTPS’i ters proxy üzerinden zorunlu kılın, `FLASK_ENV=production` kullanın ve `SECRET_KEY` ile veritabanı kimlik bilgilerini asla depoya eklemeyin.

## Sağlık kontrolü

`GET /health`, veritabanı erişimini kontrol eder ve yalnızca genel durum bilgisini döndürür. Hata ayrıntıları veya ortam değişkenleri açığa çıkarılmaz.

## Yol haritası

- [ ] Süreli indirme bağlantıları ve otomatik dosya temizleme
- [ ] Gerçek nesne depolama (S3 uyumlu servis) desteği
- [ ] Veritabanı migration’ları ve test kapsamı
- [ ] PCI-DSS uyumlu ödeme sağlayıcısı ile premium akışı

## Lisans

Bu proje [MIT License](LICENSE) ile lisanslanmıştır.
