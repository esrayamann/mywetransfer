from flask import Flask, request, redirect, url_for, send_from_directory, session, render_template, flash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import smtplib
import logging

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__)

# Database configuration with fallback
database_url = os.getenv('DATABASE_URL')
if not database_url:
    logger.error("DATABASE_URL not found in environment variables!")
    database_url = "sqlite:///app.db"  # Fallback to SQLite for development

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Secret key configuration with fallback
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    logger.warning("SECRET_KEY not found, using default key!")
    secret_key = "dev-secret-key-change-in-production"

app.config['SECRET_KEY'] = secret_key
app.config['UPLOAD_FOLDER'] = 'uploads'

db = SQLAlchemy(app)

# MODELLER
class File(db.Model):
    __tablename__ = 'file'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))# Alıcı
    sender_email = db.Column(db.String(120))  # Gönderen

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    is_premium = db.Column(db.Boolean, default=False)
    storage_quota = db.Column(db.Float, default=5120)
    role = db.Column(db.String(20), default='user')

if not os.path.exists('uploads'):
    os.makedirs('uploads')


# ANA SAYFA
@app.route('/')
def home():
    return render_template('base.html')

# HEALTH CHECK
@app.route('/health')
def health_check():
    try:
        # Test database connection
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        db_status = "OK"
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        db_status = f"ERROR: {str(e)}"
    
    return {
        'status': 'OK',
        'database': db_status,
        'env_vars': {
            'DATABASE_URL_set': bool(os.getenv('DATABASE_URL')),
            'SECRET_KEY_set': bool(os.getenv('SECRET_KEY')),
            'MAIL_USERNAME_set': bool(os.getenv('MAIL_USERNAME')),
            'MAIL_PASSWORD_set': bool(os.getenv('MAIL_PASSWORD'))
        }
    }



# KAYIT OL
@app.route('/register', methods=['GET', 'POST'])
def register():
    try:
        if request.method == 'POST':
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']

            # Check if user already exists
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash("Bu kullanıcı adı zaten kullanılıyor.", "error")
                return render_template('register.html', error="Bu kullanıcı adı zaten kullanılıyor.")

            existing_email = User.query.filter_by(email=email).first()
            if existing_email:
                flash("Bu email adresi zaten kullanılıyor.", "error")
                return render_template('register.html', error="Bu email adresi zaten kullanılıyor.")

            new_user = User(username=username, email=email, password=password)
            db.session.add(new_user)
            db.session.commit()

            logger.info(f"New user registered: {username}")
            flash("Kayıt başarılı! Giriş yapabilirsiniz.", "success")
            return redirect(url_for('login'))
        
        return render_template('register.html')
    
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        db.session.rollback()
        flash("Kayıt olurken bir hata oluştu. Lütfen tekrar deneyin.", "error")
        return render_template('register.html', error="Sistem hatası. Lütfen tekrar deneyin.")


# GİRİŞ
@app.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            
            logger.info(f"Login attempt for user: {username}")
            
            user = User.query.filter_by(username=username, password=password).first()

            if user:
                session['username'] = user.username
                logger.info(f"User {username} logged in successfully")

                if user.role == 'admin':
                    return redirect(url_for('admin_panel'))
                else:
                    return redirect(url_for('user_home'))
            else:
                logger.warning(f"Failed login attempt for user: {username}")
                flash("Geçersiz kullanıcı adı veya şifre.", "error")
                return render_template('login.html', error="Geçersiz kullanıcı adı veya şifre.")
        
        return render_template('login.html')
    
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        flash("Giriş yapılırken bir hata oluştu. Lütfen tekrar deneyin.", "error")
        return render_template('login.html', error="Sistem hatası. Lütfen tekrar deneyin.")

# ÇIKIŞ
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# KULLANICI ANA SAYFA
@app.route('/user_home', methods=['GET', 'POST'])
def user_home():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))

    user = User.query.filter_by(username=username).first()
    premium_status = 'Premium' if user.is_premium else 'Standart'
    return render_template('user_home.html',
                           username=user.username,
                           premium_status=premium_status,
                           storage_quota=round(user.storage_quota, 2),
                           is_premium=user.is_premium)

# ADMIN PANEL
@app.route('/admin')
def admin_panel():
    users = User.query.all()
    return render_template('admin.html', users=users)

# Adminde ROL DEĞİŞTİR
@app.route('/change_role/<int:user_id>', methods=['POST'])
def change_role(user_id):
    user = User.query.get(user_id)
    if not user:
        return "Kullanıcı bulunamadı."

    new_role = request.form['role']
    if new_role in ['user', 'admin']:
        user.role = new_role
        db.session.commit()
        return redirect(url_for('admin_panel'))
    else:
        return "Geçersiz rol!"


# PREMIUM SATIN AL
@app.route('/upgrade/<username>', methods=['GET', 'POST'])
def upgrade(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return "Kullanıcı bulunamadı."
    if request.method == 'POST':
        cardholder = request.form['cardholder']
        cardnumber = request.form['cardnumber']
        expiry = request.form['expiry']
        cvv = request.form['cvv']

        user.is_premium = True
        user.storage_quota = 204800
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('upgrade.html', username=user.username)


# PREMIUM İPTAL
@app.route('/cancel/<username>', methods=['POST'])
def cancel(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return "Kullanıcı bulunamadı."
    user.is_premium = False
    user.storage_quota = 5120
    db.session.commit()
    return redirect(url_for('login'))

# ÜYE OLMADAN DOSYA GÖNDER
 @app.route('/send_file', methods=['POST'])
def send_file_route():
    try:
        # Gerekli alanları al
        sender_email = request.form.get('sender_email')
        receiver_email = request.form.get('receiver_email')
        
        # Eğer kullanıcı giriş yapmışsa, gönderen email olarak kullanıcının emailini kullan
        if 'username' in session:
            user = User.query.filter_by(username=session['username']).first()
            if user:
                sender_email = user.email  # Giriş yapmış kullanıcının emailini kullan
        
        # Validasyonlar
        if not sender_email or not receiver_email:
            return jsonify({'error': 'Lütfen email adreslerini girin!'}), 400
            
        if 'file' not in request.files:
            return jsonify({'error': 'Lütfen bir dosya seçin!'}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Geçersiz dosya!'}), 400

        # Dosya boyutu kontrolü (maksimum 2GB)
        max_size = 2 * 1024 * 1024 * 1024  # 2GB
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > max_size:
            return jsonify({'error': 'Dosya boyutu çok büyük! Maksimum 2GB'}), 400

        # Dosyayı kaydet
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Veritabanına kaydet
        new_file = File(
            filename=filename,
            email=receiver_email,
            sender_email=sender_email,
            user_id=user.id if 'username' in session else None  # Kullanıcı giriş yapmışsa user_id'yi kaydet
        )
        db.session.add(new_file)
        db.session.commit()

        # İndirme linki oluştur
        download_link = url_for('download_file', filename=filename, _external=True)
        
        # E-posta gönder (opsiyonel)
        try:
            send_download_link_mail(receiver_email, filename, download_link)
            if sender_email != receiver_email:  # Kendine göndermiyorsa gönderene de bilgi ver
                send_upload_confirmation(sender_email, filename)
        except Exception as e:
            logger.error(f"E-posta gönderilemedi: {str(e)}")

        return jsonify({
            'success': True,
            'download_link': download_link,
            'message': 'Dosya başarıyla gönderildi!'
        })

    except Exception as e:
        logger.error(f"Dosya gönderilirken hata: {str(e)}")
        return jsonify({'error': 'Dosya gönderilirken bir hata oluştu!'}), 500
    
# DOSYA YÜKLE
@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        username = session.get('username')
        if not username:
            return redirect(url_for('login'))
        
        user = User.query.filter_by(username=username).first()
        if not user:
            flash("Kullanıcı bulunamadı!", "error")
            return redirect(url_for('user_home'))

        file = request.files['file']
        if not file or file.filename == '':
            flash("Lütfen bir dosya seçin!", "error")
            return redirect(url_for('user_home'))

        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        
        # Premium kullanıcılar için limit kontrolü yok
        if not user.is_premium and user.storage_quota < file_size_mb:
            os.remove(filepath)
            flash("Yetersiz alan! Premium'a yükseltin.", "error")
            return redirect(url_for('user_home'))

        # Premium olmayan kullanıcılar için alan düşür
        if not user.is_premium:
            user.storage_quota -= file_size_mb
        
        db.session.add(File(filename=filename, email=user.email))
        db.session.commit()
        
        flash(f"{filename} başarıyla yüklendi!", "success")
        logger.info(f"User {username} uploaded file: {filename}")
        
        return redirect(url_for('user_home'))
        
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        flash("Dosya yüklenirken bir hata oluştu!", "error")
        return redirect(url_for('user_home'))


# DOSYA İNDİR
@app.route('/download/<filename>')
def download_file(filename):
    file_entry = File.query.filter_by(filename=filename).first()
    if file_entry:
        send_download_notification(file_entry)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# FORM
@app.route('/form')
def upload_form():
    return '''
    <h2>Dosya Yükle</h2>
    <form method="post" action="/upload" enctype="multipart/form-data">
      <label>Dosya seç:</label><br>
      <input type="file" name="file"><br><br>
      <button type="submit">Yükle</button>
    </form>
    '''


# SMTP FONKSİYONLARI
def send_download_mail(to_email, filename):
    sender_email = os.getenv("MAIL_USERNAME")
    password = os.getenv("MAIL_PASSWORD")
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = 'Dosyanız indirildi'
    msg.attach(MIMEText(f'{filename} dosyanız indirildi.', 'plain'))
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_email, password)
        server.send_message(msg)


def send_download_link_mail(to_email, filename, link):
    sender_email = os.getenv("MAIL_USERNAME")
    password = os.getenv("MAIL_PASSWORD")
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = to_email
    msg['Subject'] = 'Yeni dosya yüklendi!'
    msg.attach(MIMEText(f'{filename} dosyası yüklendi. İndirme linki: {link}', 'plain'))
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_email, password)
        server.send_message(msg)

def send_download_notification(file_entry):
    sender_email = file_entry.sender_email
    receiver_email = file_entry.email
    filename = file_entry.filename

    sender_address = os.getenv("MAIL_USERNAME")
    password = os.getenv("MAIL_PASSWORD")

    # Alıcıya bilgi
    msg_receiver = MIMEMultipart()
    msg_receiver['From'] = sender_address
    msg_receiver['To'] = receiver_email
    msg_receiver['Subject'] = 'Dosyanız İndirildi!'
    msg_receiver.attach(MIMEText(
        f'{filename} dosyası başarıyla indirildi.', 'plain'))

    # Gönderene bilgi
    msg_sender = MIMEMultipart()
    msg_sender['From'] = sender_address
    msg_sender['To'] = sender_email
    msg_sender['Subject'] = 'Gönderdiğiniz Dosya İndirildi!'
    msg_sender.attach(MIMEText(
        f'{filename} isimli gönderdiğiniz dosya {receiver_email} tarafından indirildi.', 'plain'))

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_address, password)
        server.send_message(msg_receiver)
        server.send_message(msg_sender)

def send_upload_confirmation(sender_email, filename):
    sender_address = os.getenv("MAIL_USERNAME")
    password = os.getenv("MAIL_PASSWORD")

    msg = MIMEMultipart()
    msg['From'] = sender_address
    msg['To'] = sender_email
    msg['Subject'] = 'Dosya Gönderim Onayı'
    
    body = f"""
    <p>Merhaba,</p>
    <p><strong>{filename}</strong> dosyanız başarıyla gönderilmiştir.</p>
    <p>Teşekkür ederiz.</p>
    """
    
    msg.attach(MIMEText(body, 'html'))
    
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(sender_address, password)
        server.send_message(msg)
        
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
