#!/bin/bash

# MyWeTransfer Environment Setup Script
# Bu script .env dosyasını oluşturur

echo "🔧 MyWeTransfer Environment Setup"
echo "================================="

# .env dosyası oluştur
echo "📝 .env dosyası oluşturuluyor..."

cat > .env << 'EOF'
# Database Configuration
DATABASE_URL=postgresql://mywetransfer_user:your_secure_password@localhost:5432/mywetransfer

# Flask Secret Key
SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')

# Email Configuration
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Flask Configuration
FLASK_ENV=production
FLASK_DEBUG=False
EOF

echo "✅ .env dosyası oluşturuldu!"
echo ""
echo "⚠️  Lütfen .env dosyasını düzenleyin:"
echo "   - DATABASE_URL'deki şifreyi değiştirin"
echo "   - MAIL_USERNAME ve MAIL_PASSWORD değerlerini güncelleyin"
echo ""
echo "📝 Düzenleme komutu:"
echo "   nano .env"
echo ""
echo "🔍 Dosya içeriğini kontrol etmek için:"
echo "   cat .env" 