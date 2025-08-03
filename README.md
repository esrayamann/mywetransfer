# MyWeTransfer - Dosya Paylaşım Uygulaması

## 🚀 Kurulum

### 1. Gereksinimler
- Python 3.8+
- PostgreSQL (veya SQLite)
- Gmail hesabı (email gönderimi için)

### 2. Environment Variables
Proje kök dizininde `.env` dosyası oluşturun:

```bash
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/database_name

# Flask Secret Key
SECRET_KEY=your-super-secret-key-change-this-in-production

# Email Configuration
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=False
```

### 3. Kurulum Adımları
```bash
# Virtual environment oluştur
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

# Dependencies yükle
pip install -r requirements.txt

# Database oluştur
python app.py
```

### 4. Canlı Sunucu İçin
- `.env` dosyasını sunucuya yükleyin
- PostgreSQL bağlantı bilgilerini güncelleyin
- `FLASK_ENV=production` olarak ayarlayın

## 🔧 Sorun Giderme

### Internal Server Error
1. `/health` endpoint'ini kontrol edin
2. Database bağlantısını test edin
3. Log dosyalarını kontrol edin

### Database Bağlantı Sorunu
- PostgreSQL servisinin çalıştığından emin olun
- DATABASE_URL formatını kontrol edin
- Firewall ayarlarını kontrol edin

## 📍 Canlı Sunucu Adresleri
- Ana sunucu: http://93.115.79.35/
- Ngrok tünel: https://faccc11d33b3.ngrok-free.app/
