from flask import Flask, abort, request, redirect, url_for, send_from_directory, session, render_template, flash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import os
import smtplib
import logging
from werkzeug.security import generate_password_hash, check_password_hash
import zipfile
import tempfile
import uuid
import re
import hmac
import secrets
import click
from datetime import timedelta
from functools import wraps
from pathlib import Path
from sqlalchemy import or_, text

load_dotenv()

# Never log database URLs, mail credentials, or uploaded file contents.
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MAX_UPLOAD_MB = 100
ALLOWED_EXTENSIONS = {
    '.avi', '.csv', '.doc', '.docx', '.jpg', '.jpeg', '.mov', '.mp3', '.mp4',
    '.pdf', '.png', '.ppt', '.pptx', '.rar', '.txt', '.xls', '.xlsx', '.zip',
}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]{3,50}$")


def positive_int_from_env(name, default):
    try:
        return max(1, int(os.getenv(name, default)))
    except (TypeError, ValueError):
        logger.warning("Invalid %s value; using the default.", name)
        return default


is_production = os.getenv('FLASK_ENV', '').lower() == 'production'
secret_key = os.getenv('SECRET_KEY')
if not secret_key:
    if is_production:
        raise RuntimeError('SECRET_KEY must be set when FLASK_ENV=production.')
    secret_key = secrets.token_urlsafe(32)
    logger.warning('SECRET_KEY is not set; using an ephemeral development key.')

upload_directory = Path(os.getenv('UPLOAD_FOLDER', BASE_DIR / 'uploads')).resolve()
upload_directory.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config.from_mapping(
    SECRET_KEY=secret_key,
    SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'sqlite:///app.db'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    UPLOAD_FOLDER=str(upload_directory),
    MAX_CONTENT_LENGTH=positive_int_from_env('MAX_UPLOAD_MB', DEFAULT_MAX_UPLOAD_MB) * 1024 * 1024,
    MAX_FILES_PER_TRANSFER=positive_int_from_env('MAX_FILES_PER_TRANSFER', 25),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=is_production,
)

db = SQLAlchemy(app)

# MODELLER
class File(db.Model):
    __tablename__ = 'files'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    sender_email = db.Column(db.String(120))  
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)  # Kullanıcı ID 

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)
    is_premium = db.Column(db.Boolean, default=False)
    storage_quota = db.Column(db.Float, default=5120)
    role = db.Column(db.String(20), default='user')

def current_user():
    user_id = session.get('user_id')
    return db.session.get(User, user_id) if user_id else None


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not current_user():
            session.clear()
            flash('Bu sayfayı görüntülemek için giriş yapın.', 'error')
            return redirect(url_for('login'))
        return view(*args, **kwargs)
    return wrapped_view


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped_view(*args, **kwargs):
        if current_user().role != 'admin':
            abort(403)
        return view(*args, **kwargs)
    return wrapped_view


def csrf_token():
    token = session.get('_csrf_token')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf_token'] = token
    return token


app.jinja_env.globals['csrf_token'] = csrf_token


@app.before_request
def protect_against_csrf():
    if request.method == 'POST':
        session_token = session.get('_csrf_token')
        submitted_token = request.form.get('csrf_token', '')
        if not session_token or not hmac.compare_digest(session_token, submitted_token):
            abort(400, description='Geçersiz veya süresi dolmuş form isteği.')


@app.errorhandler(RequestEntityTooLarge)
def handle_upload_too_large(_error):
    limit_mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    return render_template('error.html', error_message=f'Dosya boyutu sınırı aşıldı. Maksimum {limit_mb} MB yükleyebilirsiniz.'), 413


def is_valid_email(value):
    return bool(value and EMAIL_PATTERN.fullmatch(value))


def allowed_file(filename):
    return Path(secure_filename(filename)).suffix.lower() in ALLOWED_EXTENSIONS


def uploaded_file_size(file_storage):
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    return size


def stored_filename(filename):
    return f"{uuid.uuid4().hex}{Path(secure_filename(filename)).suffix.lower()}"


def mail_is_configured():
    return bool(os.getenv('MAIL_USERNAME') and os.getenv('MAIL_PASSWORD'))

# ANA SAYFA
@app.route('/')
def home():
    return render_template('base.html')

# HEALTH CHECK
@app.route('/health')
def health_check():
    try:
        db.session.execute(text('SELECT 1'))
    except Exception:
        logger.exception('Health check database connection failed.')
        return {'status': 'degraded', 'database': 'unavailable'}, 503
    return {'status': 'ok', 'database': 'ok'}



@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    username = request.form.get('username', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    if not USERNAME_PATTERN.fullmatch(username):
        flash('Kullanıcı adı 3-50 karakter olmalı; yalnızca harf, rakam, nokta, tire ve alt çizgi içerebilir.', 'error')
        return render_template('register.html'), 400
    if not is_valid_email(email):
        flash('Geçerli bir e-posta adresi girin.', 'error')
        return render_template('register.html'), 400
    if len(password) < 8:
        flash('Şifre en az 8 karakter olmalıdır.', 'error')
        return render_template('register.html'), 400
    if User.query.filter(or_(User.username == username, User.email == email)).first():
        flash('Bu kullanıcı adı veya e-posta adresi zaten kullanılıyor.', 'error')
        return render_template('register.html'), 409

    db.session.add(User(username=username, email=email, password=generate_password_hash(password)))
    db.session.commit()
    logger.info('A new account was registered.')
    flash('Kayıt başarılı. Giriş yapabilirsiniz.', 'success')
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    identifier = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    user = User.query.filter(or_(User.username == identifier, User.email == identifier.lower())).first()
    if not user or not check_password_hash(user.password, password):
        logger.warning('Failed login attempt.')
        flash('Geçersiz kullanıcı adı veya şifre.', 'error')
        return render_template('login.html'), 401

    session.clear()
    session['user_id'] = user.id
    session.permanent = True
    logger.info('User logged in.')
    return redirect(url_for('admin_panel' if user.role == 'admin' else 'user_home'))

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    flash('Güvenle çıkış yaptınız.', 'success')
    return redirect(url_for('login'))

@app.route('/user_home')
@login_required
def user_home():
    user = current_user()
    premium_status = 'Premium' if user.is_premium else 'Standart'
    return render_template('user_home.html',
                           username=user.username,
                           user_email=user.email,
                           premium_status=premium_status,
                           storage_quota=round(user.storage_quota, 2),
                           is_premium=user.is_premium,
                           max_upload_mb=app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024))

@app.route('/admin')
@admin_required
def admin_panel():
    users = User.query.order_by(User.id).all()
    return render_template('admin.html', users=users)

@app.route('/change_role/<int:user_id>', methods=['POST'])
@admin_required
def change_role(user_id):
    user = db.session.get(User, user_id)
    new_role = request.form.get('role')
    if not user or new_role not in {'user', 'admin'}:
        abort(400)
    if user.id == current_user().id and new_role != 'admin':
        flash('Kendi yönetici yetkinizi kaldıramazsınız.', 'error')
        return redirect(url_for('admin_panel'))
    user.role = new_role
    db.session.commit()
    flash('Kullanıcı rolü güncellendi.', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/upgrade')
@login_required
def upgrade():
    return render_template('upgrade.html', username=current_user().username)

# ÜYE OLMADAN DOSYA GÖNDER
@app.route('/send_file', methods=['POST'])
def send_file_route():
    sender_email = request.form.get('sender_email', '').strip().lower()
    receiver_email = request.form.get('receiver_email', '').strip().lower()
    user = current_user()
    if user:
        sender_email = user.email
    if not is_valid_email(sender_email) or not is_valid_email(receiver_email):
        return render_template('error.html', error_message='Geçerli gönderen ve alıcı e-posta adresleri girin.'), 400

    files = [file for file in request.files.getlist('file') if file and file.filename]
    if not files:
        return render_template('error.html', error_message='En az bir dosya seçin.'), 400
    if len(files) > app.config['MAX_FILES_PER_TRANSFER']:
        return render_template('error.html', error_message='Bu aktarımda çok fazla dosya var.'), 400
    if any(not allowed_file(file.filename) for file in files):
        return render_template('error.html', error_message='İzin verilmeyen bir dosya türü seçildi.'), 400
    if sum(uploaded_file_size(file) for file in files) > app.config['MAX_CONTENT_LENGTH']:
        return render_template('error.html', error_message='Toplam dosya boyutu sınırı aşıyor.'), 413

    archive_filename = f'transfer-{uuid.uuid4().hex}.zip'
    archive_path = upload_directory / archive_filename
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as archive:
                for index, file in enumerate(files):
                    safe_name = secure_filename(file.filename)
                    if not safe_name:
                        abort(400, description='Geçersiz dosya adı.')
                    temporary_path = Path(temp_dir) / f'{index}-{safe_name}'
                    file.save(temporary_path)
                    archive.write(temporary_path, arcname=safe_name)
        db.session.add(File(filename=archive_filename, email=receiver_email, sender_email=sender_email, user_id=user.id if user else None))
        db.session.commit()
    except Exception:
        db.session.rollback()
        archive_path.unlink(missing_ok=True)
        logger.exception('File transfer could not be created.')
        return render_template('error.html', error_message='Dosya gönderilirken bir hata oluştu.'), 500

    download_link = url_for('download_file', filename=archive_filename, _external=True)
    if mail_is_configured():
        try:
            send_download_link_mail(receiver_email, archive_filename, download_link)
            if sender_email != receiver_email:
                send_upload_confirmation(sender_email, archive_filename)
        except Exception:
            logger.exception('Transfer email could not be sent.')
    return render_template('success.html', download_link=download_link)
  
# DOSYA YÜKLE
@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    user = current_user()
    file = request.files.get('file')
    if not file or not file.filename:
        flash('Lütfen bir dosya seçin.', 'error')
        return redirect(url_for('user_home'))
    if not allowed_file(file.filename):
        flash('Bu dosya türüne izin verilmiyor.', 'error')
        return redirect(url_for('user_home'))

    file_size_mb = uploaded_file_size(file) / (1024 * 1024)
    if file_size_mb > app.config['MAX_CONTENT_LENGTH'] / (1024 * 1024):
        flash('Dosya boyutu sınırı aşıyor.', 'error')
        return redirect(url_for('user_home'))
    if not user.is_premium and user.storage_quota < file_size_mb:
        flash('Yetersiz alan. Premium planlar şu anda kullanıma kapalıdır.', 'error')
        return redirect(url_for('user_home'))

    filename = stored_filename(file.filename)
    filepath = upload_directory / filename
    try:
        file.save(filepath)
        if not user.is_premium:
            user.storage_quota -= file_size_mb
        db.session.add(File(filename=filename, email=user.email, sender_email=user.email, user_id=user.id))
        db.session.commit()
    except Exception:
        db.session.rollback()
        filepath.unlink(missing_ok=True)
        logger.exception('Authenticated upload failed.')
        flash('Dosya yüklenirken bir hata oluştu.', 'error')
        return redirect(url_for('user_home'))

    flash('Dosyanız güvenle yüklendi.', 'success')
    return redirect(url_for('user_home'))


# DOSYA İNDİR
@app.route('/download/<filename>')
def download_file(filename):
    file_entry = File.query.filter_by(filename=filename).first_or_404()
    if not (upload_directory / file_entry.filename).is_file():
        abort(404)
    send_download_notification(file_entry)
    return send_from_directory(app.config['UPLOAD_FOLDER'], file_entry.filename, as_attachment=True)


# FORM
@app.route('/form')
@login_required
def upload_form():
    return render_template('upload_form.html')


# SMTP FONKSİYONLARI
def send_email(to_email, subject, body, subtype='plain'):
    if not mail_is_configured():
        raise RuntimeError('Email delivery is not configured.')
    message = MIMEMultipart()
    message['From'] = os.getenv('MAIL_USERNAME')
    message['To'] = to_email
    message['Subject'] = subject
    message.attach(MIMEText(body, subtype))
    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(os.getenv('MAIL_USERNAME'), os.getenv('MAIL_PASSWORD'))
        server.send_message(message)


def send_download_link_mail(to_email, filename, link):
    send_email(to_email, 'Yeni dosya yüklendi!', f'{filename} dosyası yüklendi. İndirme linki: {link}')


def send_download_notification(file_entry):
    if not file_entry.sender_email or not mail_is_configured():
        return
    body = (
        '<p>Merhaba,</p>'
        f'<p>Gönderdiğiniz <strong>{file_entry.filename}</strong> isimli dosya '
        f'<strong>{file_entry.email}</strong> tarafından indirildi.</p>'
    )
    try:
        send_email(file_entry.sender_email, 'Gönderdiğiniz Dosya İndirildi!', body, 'html')
    except Exception:
        logger.exception('Download notification could not be sent.')


def send_upload_confirmation(sender_email, filename):
    body = f'<p>Merhaba,</p><p><strong>{filename}</strong> dosyanız başarıyla gönderilmiştir.</p>'
    send_email(sender_email, 'Dosya Gönderim Onayı', body, 'html')


@app.cli.command('init-db')
def init_db():
    """Create database tables for a local or first-time deployment."""
    db.create_all()
    click.echo('Database tables are ready.')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
