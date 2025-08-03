#!/bin/bash

# MyWeTransfer Deployment Script
# Bu script canlı sunucuda uygulamayı kurar ve çalıştırır

set -e  # Hata durumunda script'i durdur

echo "🚀 MyWeTransfer Deployment Script"
echo "=================================="

# 1. Gerekli paketleri yükle
echo "📦 Sistem paketleri güncelleniyor..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv postgresql postgresql-contrib nginx

# 2. PostgreSQL kurulumu
echo "🗄️ PostgreSQL kurulumu..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 3. Database kullanıcısı oluştur
echo "👤 Database kullanıcısı oluşturuluyor..."
sudo -u postgres psql -c "CREATE DATABASE mywetransfer;"
sudo -u postgres psql -c "CREATE USER mywetransfer_user WITH PASSWORD 'your_secure_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE mywetransfer TO mywetransfer_user;"

# 4. Python virtual environment oluştur
echo "🐍 Python virtual environment oluşturuluyor..."
python3 -m venv venv
source venv/bin/activate

# 5. Python dependencies yükle
echo "📚 Python paketleri yükleniyor..."
pip install --upgrade pip
pip install -r requirements.txt

# 6. .env dosyası oluştur (kullanıcı düzenleyecek)
echo "⚙️ .env dosyası oluşturuluyor..."
cat > .env << EOF
# Database Configuration
DATABASE_URL=postgresql://mywetransfer_user:your_secure_password@localhost:5432/mywetransfer

# Flask Secret Key (güvenli bir key oluşturun)
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')

# Email Configuration
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=False
EOF

echo "⚠️  Lütfen .env dosyasını düzenleyin:"
echo "   - MAIL_USERNAME ve MAIL_PASSWORD değerlerini güncelleyin"
echo "   - DATABASE_URL'deki şifreyi değiştirin"

# 7. Database tablolarını oluştur
echo "🗃️ Database tabloları oluşturuluyor..."
python3 -c "
from app import app, db
with app.app_context():
    db.create_all()
    print('Database tabloları oluşturuldu!')
"

# 8. Gunicorn kurulumu
echo "🦄 Gunicorn kurulumu..."
pip install gunicorn

# 9. Systemd service dosyası oluştur
echo "🔧 Systemd service oluşturuluyor..."
sudo tee /etc/systemd/system/mywetransfer.service > /dev/null << EOF
[Unit]
Description=MyWeTransfer Flask Application
After=network.target

[Service]
User=$USER
WorkingDirectory=$(pwd)
Environment="PATH=$(pwd)/venv/bin"
ExecStart=$(pwd)/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# 10. Nginx konfigürasyonu
echo "🌐 Nginx konfigürasyonu..."
sudo tee /etc/nginx/sites-available/mywetransfer > /dev/null << EOF
server {
    listen 80;
    server_name your-domain.com;  # Domain adınızı buraya yazın

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /static {
        alias $(pwd)/static;
    }
}
EOF

# 11. Nginx site'ını aktifleştir
sudo ln -sf /etc/nginx/sites-available/mywetransfer /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

# 12. Firewall ayarları
echo "🔥 Firewall ayarları..."
sudo ufw allow 80
sudo ufw allow 443
sudo ufw allow 22

# 13. Service'leri başlat
echo "🚀 Servisler başlatılıyor..."
sudo systemctl daemon-reload
sudo systemctl enable mywetransfer
sudo systemctl start mywetransfer

# 14. Test
echo "🧪 Uygulama test ediliyor..."
sleep 5
curl -f http://localhost/health || echo "❌ Uygulama test edilemedi!"

echo ""
echo "🎉 Deployment tamamlandı!"
echo ""
echo "📋 Sonraki adımlar:"
echo "1. .env dosyasını düzenleyin"
echo "2. Domain adınızı nginx konfigürasyonunda güncelleyin"
echo "3. SSL sertifikası ekleyin (Let's Encrypt)"
echo "4. Uygulamayı test edin: http://your-domain.com"
echo ""
echo "🔧 Yararlı komutlar:"
echo "   sudo systemctl status mywetransfer  # Uygulama durumu"
echo "   sudo systemctl restart mywetransfer # Uygulamayı yeniden başlat"
echo "   sudo journalctl -u mywetransfer -f  # Log'ları izle" 