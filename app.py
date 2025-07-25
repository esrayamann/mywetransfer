from flask import Flask, request, redirect, url_for, send_from_directory, session, render_template
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import os
import smtplib

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
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



# KAYIT OL
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))
    return render_template('register.html')


# GİRİŞ
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session['username'] = user.username

            if user.role == 'admin':
                return redirect(url_for('admin_panel'))
            else:
                return redirect(url_for ('user_home'))

        return "Geçersiz kullanıcı adı veya şifre."
    return render_template('login.html')

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
@app.route('/send_file', methods=['GET', 'POST'])
def send_file_route():
    if request.method == 'POST':
        sender_email = request.form['sender_email']
        receiver_email = request.form['receiver_email']
        file = request.files['file']

        filename = file.filename
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        new_file = File(
            filename=filename,
            email=receiver_email,
            sender_email=sender_email
        )
        db.session.add(new_file)
        db.session.commit()

        download_link = f"http://127.0.0.1:5000/download/{filename}"
        send_download_link_mail(receiver_email, filename, download_link)

        # --- Burada artık direkt string döndürmek yerine template render edelim ---
        return render_template('success.html', download_link=download_link)

    return render_template('send_file.html')


# DOSYA YÜKLE
@app.route('/upload', methods=['POST'])
def upload_file():
    username = session.get('username')
    if not username:
        return redirect(url_for('login'))
    user = User.query.filter_by(username=username).first()
    if not user:
        return "Kullanıcı bulunamadı!"

    file = request.files['file']
    filename = file.filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
    if user.storage_quota < file_size_mb:
        os.remove(filepath)
        return "Yetersiz alan!"

    user.storage_quota -= file_size_mb
    db.session.add(File(filename=filename, email=user.email))
    db.session.commit()
    return f"{filename} yüklendi. Kalan alan: {round(user.storage_quota, 2)} MB"


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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
