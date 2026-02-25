from flask import Flask, request, render_template, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, or_, and_
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import requests

basedir = os.path.abspath(os.path.dirname(__file__))
instance_folder = os.path.join(basedir, 'instance')
os.makedirs(instance_folder, exist_ok=True)
db_path = os.path.join(instance_folder, 'datubaze.db')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '555555'

# OpenAI API Key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', 'your-api-key-here')

db = SQLAlchemy(app)

class Lietotaji(db.Model):
    __tablename__ = 'Lietotaji'
    id = db.Column(db.Integer, primary_key=True)
    lietotajvards = db.Column(db.String(80), unique=True, nullable=False)
    parole = db.Column(db.String(255), nullable=False)
    vards = db.Column(db.String(80), nullable=False)
    uzvards = db.Column(db.String(80), nullable=False)
    loma = db.Column(db.String(80), nullable=False)
    konta_bilde = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    epasts = db.Column(db.String(120), nullable=False, unique=True)
    ir_apstiprinats = db.Column(db.Boolean, default=True)
    reputacija = db.Column(db.Integer, default=0)

class Diskusijas(db.Model):
    __tablename__ = 'Diskusijas'
    id = db.Column(db.Integer, primary_key=True)
    virsraksts = db.Column(db.String(200), nullable=False)
    saturs = db.Column(db.Text, nullable=False)
    lietotaja_id = db.Column(db.Integer, db.ForeignKey('Lietotaji.id'), nullable=False)
    datums = db.Column(db.DateTime, default=datetime.utcnow)
    ir_redigets = db.Column(db.Boolean, default=False)
    redigets_datums = db.Column(db.DateTime, nullable=True)
    ir_piefikseta = db.Column(db.Boolean, default=False)
    ir_slegta = db.Column(db.Boolean, default=False)
    komentari = db.relationship('Komentari', backref='diskusija', lazy=True, cascade='all, delete-orphan')
    lietotajs = db.relationship('Lietotaji', backref='diskusijas')
    patikumi = db.relationship('DiskusijaPatikumi', backref='diskusija', lazy=True, cascade='all, delete-orphan')

class Komentari(db.Model):
    __tablename__ = 'Komentari'
    id = db.Column(db.Integer, primary_key=True)
    saturs = db.Column(db.Text, nullable=False)
    lietotaja_id = db.Column(db.Integer, db.ForeignKey('Lietotaji.id'), nullable=False)
    diskusijas_id = db.Column(db.Integer, db.ForeignKey('Diskusijas.id'), nullable=False)
    datums = db.Column(db.DateTime, default=datetime.utcnow)
    ir_redigets = db.Column(db.Boolean, default=False)
    redigets_datums = db.Column(db.DateTime, nullable=True)
    lietotajs = db.relationship('Lietotaji', backref='komentari')
    patikumi = db.relationship('KomentaraPatikumi', backref='komentars', lazy=True, cascade='all, delete-orphan')

class DiskusijaPatikumi(db.Model):
    __tablename__ = 'DiskusijaPatikumi'
    id = db.Column(db.Integer, primary_key=True)
    diskusijas_id = db.Column(db.Integer, db.ForeignKey('Diskusijas.id'), nullable=False)
    lietotaja_id = db.Column(db.Integer, db.ForeignKey('Lietotaji.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('diskusijas_id', 'lietotaja_id', name='unique_diskusija_patikums'),)

class KomentaraPatikumi(db.Model):
    __tablename__ = 'KomentaraPatikumi'
    id = db.Column(db.Integer, primary_key=True)
    komentara_id = db.Column(db.Integer, db.ForeignKey('Komentari.id'), nullable=False)
    lietotaja_id = db.Column(db.Integer, db.ForeignKey('Lietotaji.id'), nullable=False)
    __table_args__ = (db.UniqueConstraint('komentara_id', 'lietotaja_id', name='unique_komentars_patikums'),)

class Notikumi(db.Model):
    __tablename__ = 'Notikumi'
    id = db.Column(db.Integer, primary_key=True)
    nosaukums = db.Column(db.String(200), nullable=False)
    apraksts = db.Column(db.Text, nullable=True)
    datums = db.Column(db.DateTime, nullable=False)
    tips = db.Column(db.String(50), nullable=False)
    raditas_datums = db.Column(db.DateTime, default=datetime.utcnow)

class Patikumi(db.Model):
    __tablename__ = 'Patikumi'
    id = db.Column(db.Integer, primary_key=True)
    skaits = db.Column(db.Integer, default=0)

class Patikumi_lietotajs(db.Model):
    __tablename__ = 'Patikumi_lietotajs'
    id = db.Column(db.Integer, primary_key=True)
    lietotaja_id = db.Column(db.Integer, db.ForeignKey('Lietotaji.id'), unique=True, nullable=False)


UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

def moderate_content(content):
    """
    Check content with OpenAI's moderation API
    Returns: (is_safe, reason) tuple
    """
    if not OPENAI_API_KEY or OPENAI_API_KEY == 'your-api-key-here':
        return True, "No API key configured"
    
    try:
        response = requests.post(
            "https://api.openai.com/v1/moderations",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"input": content}
        )
        
        if response.status_code == 200:
            result = response.json()
            flagged = result['results'][0]['flagged']
            categories = result['results'][0]['categories']
            
            if flagged:
                # Find which categories were flagged
                flagged_items = [cat for cat, value in categories.items() if value]
                reason = f"Saturs ir marķēts kā nepieņemams: {', '.join(flagged_items)}"
                return False, reason
            return True, ""
        else:
            return True, "Moderation API unavailable"
    except Exception as e:
        print(f"Moderation error: {e}")
        return True, ""

def calculate_user_reputation(user_id):
    """Calculate total reputation for a user based on likes"""
    # Count likes on user's discussions
    discussion_likes = db.session.query(DiskusijaPatikumi).join(
        Diskusijas, DiskusijaPatikumi.diskusijas_id == Diskusijas.id
    ).filter(Diskusijas.lietotaja_id == user_id).count()
    
    # Count likes on user's comments
    comment_likes = db.session.query(KomentaraPatikumi).join(
        Komentari, KomentaraPatikumi.komentara_id == Komentari.id
    ).filter(Komentari.lietotaja_id == user_id).count()
    
    return discussion_likes + comment_likes

@app.route("/")
def index():
    patikums = get_patikumi()
    
    # Get all discussions sorted - pinned first, then by date
    diskusijas = Diskusijas.query.order_by(
        Diskusijas.ir_piefikseta.desc(),
        Diskusijas.datums.desc()
    ).all()
    
    # Get upcoming events
    notikumi = Notikumi.query.filter(
        Notikumi.datums >= datetime.utcnow()
    ).order_by(Notikumi.datums.asc()).limit(5).all()
    
    return render_template(
        "index.html", 
        diskusijas=diskusijas, 
        patikumi=patikums.skaits, 
        ir_piesledzis='lietotajvards' in session,
        Notikumi=notikumi
    )

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        lietotajvards = request.form.get("lietotajvards")
        parole = request.form.get("parole")
        vards = request.form.get("vards")
        uzvards = request.form.get("uzvards")
        loma = request.form.get("loma")
        epasts = request.form.get("epasts")
        if Lietotaji.query.filter_by(lietotajvards=lietotajvards).first():
            flash("Lietotājvārds jau pastāv")
        if Lietotaji.query.filter_by(epasts=epasts).first():
            flash("E-pasts jau reģistrēts")
        hashed_password = generate_password_hash(parole)
        ir_apstiprinats = True if loma != "Skolotajs" else False
        jauns_lietotajs = Lietotaji(
            lietotajvards=lietotajvards, 
            parole=hashed_password, 
            vards=vards, 
            uzvards=uzvards, 
            loma=loma, 
            epasts=epasts, 
            ir_apstiprinats=ir_apstiprinats
        )
        db.session.add(jauns_lietotajs)
        db.session.commit()
        if loma == "Skolotajs":
            flash("Jūsu konts tika izveidots! Lūdzu, gaidiet, līdz administrators apstiprinās jūsu kontu.", "info")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        lietotajvards = request.form.get("lietotajvards")
        parole = request.form.get("parole")
        lietotajs = Lietotaji.query.filter_by(lietotajvards=lietotajvards).first()
        if lietotajs and check_password_hash(lietotajs.parole, parole):
            if not lietotajs.ir_apstiprinats:
                flash("Jūsu konts vēl nav apstiprinājis administrators.", "danger")
                return redirect(url_for("login"))
            session['lietotajvards'] = lietotajvards
            session['lietotaja_id'] = lietotajs.id
            session['vards'] = lietotajs.vards
            session['konta_bilde'] = lietotajs.konta_bilde
            session['loma'] = lietotajs.loma
            return redirect(url_for("index"))
        flash("Nepareizs lietotājvārds vai parole.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Atteikšanas veiksmīga!")
    return redirect(url_for("index"))

@app.route("/diskusijas/jauna", methods=["GET", "POST"])
def jauna_diskusija():
    if 'lietotajvards' not in session:
        return redirect(url_for("login"))
    
    # Check if teacher account needs approval
    lietotajs = Lietotaji.query.get(session['lietotaja_id'])
    if lietotajs.loma == "Skolotajs" and not lietotajs.ir_apstiprinats:
        flash("Jūs varat izveidot diskusijas tikai pēc apstiprinājuma.", "danger")
        return redirect(url_for("index"))
    
    if request.method == "POST":
        virsraksts = request.form.get("virsraksts")
        saturs = request.form.get("saturs")
        
        # Check content moderation
        is_safe, reason = moderate_content(f"{virsraksts} {saturs}")
        if not is_safe:
            flash(f"Saturs nevar tikt izvietots: {reason}", "danger")
            return render_template("jauna_diskusija.html")
        
        jauna = Diskusijas(
            virsraksts=virsraksts, 
            saturs=saturs, 
            lietotaja_id=session['lietotaja_id'],
            ir_redigets=False
        )
        db.session.add(jauna)
        db.session.commit()
        return redirect(url_for("index"))
    return render_template("jauna_diskusija.html")

@app.route("/diskusijas/<int:diskusijas_id>", methods=["GET", "POST"])
def diskusija(diskusijas_id):
    diskusija = Diskusijas.query.get_or_404(diskusijas_id)
    
    if diskusija.ir_slegta and 'lietotajvards' in session:
        lietotajs = Lietotaji.query.get(session['lietotaja_id'])
        if lietotajs.id != diskusija.lietotaja_id and lietotajs.loma != 'Administrators':
            flash("Šī diskusija ir slēgta.", "info")
            return redirect(url_for("index"))
    
    if request.method == "POST":
        if 'lietotajvards' not in session:
            return redirect(url_for("login"))
        
        # Check if teacher account is verified
        lietotajs = Lietotaji.query.get(session['lietotaja_id'])
        if lietotajs.loma == "Skolotajs" and not lietotajs.ir_apstiprinats:
            flash("Jūs varat komentēt tikai pēc apstiprinājuma.", "danger")
            return redirect(url_for("diskusija", diskusijas_id=diskusijas_id))
        
        saturs = request.form.get("saturs")
        
        # Check content moderation
        is_safe, reason = moderate_content(saturs)
        if not is_safe:
            flash(f"Saturs nevar tikt izvietots: {reason}", "danger")
            return redirect(url_for("diskusija", diskusijas_id=diskusijas_id))
        
        komentars = Komentari(
            saturs=saturs, 
            lietotaja_id=session['lietotaja_id'], 
            diskusijas_id=diskusijas_id,
            ir_redigets=False
        )
        db.session.add(komentars)
        db.session.commit()
        return redirect(url_for("diskusija", diskusijas_id=diskusijas_id))
    
    return render_template(
        "diskusija.html", 
        diskusija=diskusija, 
        ir_piesledzis='lietotajvards' in session
    )

def get_patikumi():
    patikums = Patikumi.query.first()
    if not patikums:
        patikums = Patikumi(skaits=0)
        db.session.add(patikums)
        db.session.commit()
    count = Patikumi_lietotajs.query.count()
    if patikums.skaits != count:
        patikums.skaits = count
        db.session.commit()
    return patikums

@app.route("/patikt")
def patikt():
    if 'lietotajvards' not in session:
        return redirect(url_for("login"))
    lietotajs_id = session.get('lietotaja_id')
    if Patikumi_lietotajs.query.filter_by(lietotaja_id=lietotajs_id).first():
        flash("Tu jau esi šeit atstājis atzīmi 'Patīk'.")
        return redirect(url_for("index"))
    pu = Patikumi_lietotajs(lietotaja_id=lietotajs_id)
    db.session.add(pu)
    db.session.commit()
    patikums = get_patikumi()
    return redirect(url_for("index"))

@app.route('/like/diskusija/<int:diskusijas_id>', methods=['POST'])
def like_diskusija(diskusijas_id):
    if 'lietotajvards' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    lietotaja_id = session['lietotaja_id']
    diskusija = Diskusijas.query.get_or_404(diskusijas_id)
    
    # Check if already liked
    existing = DiskusijaPatikumi.query.filter_by(
        diskusijas_id=diskusijas_id, 
        lietotaja_id=lietotaja_id
    ).first()
    
    if existing:
        # Unlike
        db.session.delete(existing)
        db.session.commit()
        liked = False
    else:
        # Like
        like = DiskusijaPatikumi(diskusijas_id=diskusijas_id, lietotaja_id=lietotaja_id)
        db.session.add(like)
        db.session.commit()
        liked = True
    
    # Update user reputation
    user = Lietotaji.query.get(diskusija.lietotaja_id)
    user.reputacija = calculate_user_reputation(user.id)
    db.session.commit()
    
    like_count = DiskusijaPatikumi.query.filter_by(diskusijas_id=diskusijas_id).count()
    return jsonify({'success': True, 'liked': liked, 'like_count': like_count})

@app.route('/like/komentars/<int:komentara_id>', methods=['POST'])
def like_komentars(komentara_id):
    if 'lietotajvards' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'}), 401
    
    lietotaja_id = session['lietotaja_id']
    komentars = Komentari.query.get_or_404(komentara_id)
    
    # Check if already liked
    existing = KomentaraPatikumi.query.filter_by(
        komentara_id=komentara_id, 
        lietotaja_id=lietotaja_id
    ).first()
    
    if existing:
        # Unlike
        db.session.delete(existing)
        db.session.commit()
        liked = False
    else:
        # Like
        like = KomentaraPatikumi(komentara_id=komentara_id, lietotaja_id=lietotaja_id)
        db.session.add(like)
        db.session.commit()
        liked = True
    
    # Update user reputation
    user = Lietotaji.query.get(komentars.lietotaja_id)
    user.reputacija = calculate_user_reputation(user.id)
    db.session.commit()
    
    like_count = KomentaraPatikumi.query.filter_by(komentara_id=komentara_id).count()
    return jsonify({'success': True, 'liked': liked, 'like_count': like_count})

@app.route('/search', methods=['GET'])
def search():
    query = request.args.get('q', '').strip()
    results = {'diskusijas': [], 'komentari': [], 'lietotaji': []}
    
    if len(query) < 2:
        return render_template('search.html', query=query, results=results)
    
    # Search discussions by title and content
    diskusijas = Diskusijas.query.filter(
        or_(
            Diskusijas.virsraksts.ilike(f'%{query}%'),
            Diskusijas.saturs.ilike(f'%{query}%')
        )
    ).all()
    results['diskusijas'] = diskusijas
    
    # mekle komentarus
    komentari = Komentari.query.filter(
        Komentari.saturs.ilike(f'%{query}%')
    ).all()
    results['komentari'] = komentari
    
    # mekle kontus
    lietotaji = Lietotaji.query.filter(
        or_(
            Lietotaji.lietotajvards.ilike(f'%{query}%'),
            Lietotaji.vards.ilike(f'%{query}%'),
            Lietotaji.uzvards.ilike(f'%{query}%')
        )
    ).all()
    results['lietotaji'] = lietotaji
    
    return render_template('search.html', query=query, results=results)

@app.route('/konts', methods=['GET', 'POST'])
def konts():
    if 'lietotajvards' not in session:
        return redirect(url_for('login'))
    lietotajs = Lietotaji.query.get(session['lietotaja_id'])
    if request.method == 'POST':
        vards = request.form.get('vards')
        uzvards = request.form.get('uzvards')
        bio = request.form.get('bio')
        new_pass = request.form.get('parole')
        if vards:
            lietotajs.vards = vards
            session['vards'] = vards
        if uzvards:
            lietotajs.uzvards = uzvards
        if bio:
            lietotajs.bio = bio
        if new_pass:
            lietotajs.parole = generate_password_hash(new_pass)
        file = request.files.get('konta_bilde')
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
            filename = f"u{lietotajs.id}_{timestamp}_{filename}"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            lietotajs.konta_bilde = filename
            session['konta_bilde'] = filename
        db.session.commit()
        flash("Konts atjaunots!")
        return redirect(url_for('konts'))
    return render_template('rediget_konts.html', lietotajs=lietotajs)

@app.route('/profils/<lietotaja_vards>')
def profils(lietotaja_vards):
    lietotajs = Lietotaji.query.filter_by(lietotajvards=lietotaja_vards).first_or_404()
    
    # Calculate total reputation (likes on all posts and comments)
    lietotajs.reputacija = calculate_user_reputation(lietotajs.id)
    db.session.commit()
    
    return render_template('profils.html', lietotajs=lietotajs)

@app.route('/diskusijas/<int:diskusijas_id>/rediget', methods=['GET', 'POST'])
def rediget_diskusija(diskusijas_id):
    diskusija = Diskusijas.query.get_or_404(diskusijas_id)
    if diskusija.lietotaja_id != session.get('lietotaja_id'):
        flash("Jums nav atļaujas to rediģēt.", "danger")
        return redirect(url_for('diskusija', diskusijas_id=diskusijas_id))
    if request.method == 'POST':
        virsraksts = request.form.get('virsraksts')
        saturs = request.form.get('saturs')
        
        # Check content moderation
        is_safe, reason = moderate_content(f"{virsraksts} {saturs}")
        if not is_safe:
            flash(f"Saturs nevar tikt atjaunots: {reason}", "danger")
            return render_template('rediget_diskusija.html', diskusija=diskusija)
        
        diskusija.virsraksts = virsraksts
        diskusija.saturs = saturs
        diskusija.ir_redigets = True
        diskusija.redigets_datums = datetime.utcnow()
        db.session.commit()
        flash("Diskusija rediģēta!")
        return redirect(url_for('diskusija', diskusijas_id=diskusijas_id))
    return render_template('rediget_diskusija.html', diskusija=diskusija)

@app.route('/diskusijas/<int:diskusijas_id>/dzest', methods=['POST'])
def dzest_diskusija(diskusijas_id):
    diskusija = Diskusijas.query.get_or_404(diskusijas_id)
    if diskusija.lietotaja_id != session.get('lietotaja_id') and session.get('loma') != 'Administrators':
        flash("Jums nav atļaujas to dzēst.", "danger")
        return redirect(url_for('diskusija', diskusijas_id=diskusijas_id))
    db.session.delete(diskusija)
    db.session.commit()
    flash("Diskusija dzēsta!")
    return redirect(url_for('index'))

@app.route('/diskusijas/<int:diskusijas_id>/toggle_lock', methods=['POST'])
def toggle_lock_diskusija(diskusijas_id):
    diskusija = Diskusijas.query.get_or_404(diskusijas_id)
    lietotajs = Lietotaji.query.get(session.get('lietotaja_id'))
    
    # Only author or admin can lock
    if diskusija.lietotaja_id != session.get('lietotaja_id') and session.get('loma') != 'Administrators':
        flash("Jums nav atļaujas to darīt.", "danger")
        return redirect(url_for('diskusija', diskusijas_id=diskusijas_id))
    
    diskusija.ir_slegta = not diskusija.ir_slegta
    db.session.commit()
    status = "slēgta" if diskusija.ir_slegta else "atvērta"
    flash(f"Diskusija ir tagad {status}.", "success")
    return redirect(url_for('diskusija', diskusijas_id=diskusijas_id))

@app.route('/diskusijas/<int:diskusijas_id>/toggle_pin', methods=['POST'])
def toggle_pin_diskusija(diskusijas_id):
    if session.get('loma') != 'Administrators':
        flash("Jums nav atļaujas to darīt.", "danger")
        return redirect(url_for('index'))
    
    diskusija = Diskusijas.query.get_or_404(diskusijas_id)
    diskusija.ir_piefikseta = not diskusija.ir_piefikseta
    db.session.commit()
    status = "piefiksēta" if diskusija.ir_piefikseta else "noņemta no piefiksēšanas"
    flash(f"Diskusija ir {status}.", "success")
    return redirect(url_for('diskusija', diskusijas_id=diskusijas_id))

@app.route('/komentari/<int:komentara_id>/rediget', methods=['GET', 'POST'])
def rediget_komentars(komentara_id):
    komentars = Komentari.query.get_or_404(komentara_id)
    if komentars.lietotaja_id != session.get('lietotaja_id'):
        flash("Jums nav atļaujas to rediģēt.", "danger")
        return redirect(url_for('diskusija', diskusijas_id=komentars.diskusijas_id))
    if request.method == 'POST':
        saturs = request.form.get('saturs')
        
        # Check content moderation
        is_safe, reason = moderate_content(saturs)
        if not is_safe:
            flash(f"Saturs nevar tikt atjaunots: {reason}", "danger")
            return render_template('rediget_komentars.html', komentars=komentars)
        
        komentars.saturs = saturs
        komentars.ir_redigets = True
        komentars.redigets_datums = datetime.utcnow()
        db.session.commit()
        flash("Komentārs rediģēts!")
        return redirect(url_for('diskusija', diskusijas_id=komentars.diskusijas_id))
    return render_template('rediget_komentars.html', komentars=komentars)

@app.route('/komentari/<int:komentara_id>/dzest', methods=['POST'])
def dzest_komentars(komentara_id):
    komentars = Komentari.query.get_or_404(komentara_id)
    diskusijas_id = komentars.diskusijas_id
    if komentars.lietotaja_id != session.get('lietotaja_id') and session.get('loma') != 'Administrators':
        flash("Jums nav atļaujas to dzēst.", "danger")
        return redirect(url_for('diskusija', diskusijas_id=diskusijas_id))
    db.session.delete(komentars)
    db.session.commit()
    flash("Komentārs dzēsts!")
    return redirect(url_for('diskusija', diskusijas_id=diskusijas_id))

@app.route('/leaderboard')
def leaderboard():
    # Get top users by reputation
    top_users = Lietotaji.query.order_by(Lietotaji.reputacija.desc()).limit(50).all()
    return render_template('leaderboard.html', top_users=top_users)

@app.route('/admin/panel')
def admin_panel():
    if session.get('loma') != 'Administrators':
        flash("Jums nav piekļuves šim lapai.", "danger")
        return redirect(url_for('index'))
    neapstiprinats_lietotajss = Lietotaji.query.filter_by(ir_apstiprinats=False).all()
    neapstiprinats_skolotaji = Lietotaji.query.filter_by(loma='Skolotajs', ir_apstiprinats=False).all()
    all_lietotajss = Lietotaji.query.all()
    return render_template(
        'admin_panel.html', 
        neapstiprinats_lietotajss=neapstiprinats_lietotajss,
        neapstiprinats_skolotaji=neapstiprinats_skolotaji,
        all_lietotajss=all_lietotajss
    )

@app.route('/admin/atstiprinat/<int:lietotaja_id>', methods=['POST'])
def atstiprinat_lietotajs(lietotaja_id):
    if session.get('loma') != 'Administrators':
        flash("Jums nav atļaujas to darīt.", "danger")
        return redirect(url_for('index'))
    lietotajs = Lietotaji.query.get_or_404(lietotaja_id)
    lietotajs.ir_apstiprinats = True
    db.session.commit()
    flash(f"Lietotājs {lietotajs.lietotajvards} tika apstiprinājis!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/verificet_skolotajs/<int:lietotaja_id>', methods=['POST'])
def verificet_skolotajs(lietotaja_id):
    if session.get('loma') != 'Administrators':
        flash("Jums nav atļaujas to darīt.", "danger")
        return redirect(url_for('index'))
    
    lietotajs = Lietotaji.query.get_or_404(lietotaja_id)
    if lietotajs.loma != 'Skolotajs':
        flash("Šis lietotājs nav skolotājs.", "danger")
        return redirect(url_for('admin_panel'))
    
    lietotajs.ir_apstiprinats_skolotajs = True
    db.session.commit()
    flash(f"Skolotājs {lietotajs.lietotajvards} ir verificēts!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/dzest_lietotajs/<int:lietotaja_id>', methods=['POST'])
def dzest_lietotajs(lietotaja_id):
    if session.get('loma') != 'Administrators':
        flash("Jums nav atļaujas to darīt.", "danger")
        return redirect(url_for('index'))
    lietotajs = Lietotaji.query.get_or_404(lietotaja_id)
    db.session.delete(lietotajs)
    db.session.commit()
    flash(f"Lietotājs {lietotajs.lietotajvards} tika dzēsts!", "success")
    return redirect(url_for('admin_panel'))

@app.route('/admin/Notikumi', methods=['GET', 'POST'])
def admin_Notikumi():
    if session.get('loma') != 'Administrators':
        flash("Jums nav piekļuves šim lapai.", "danger")
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        nosaukums = request.form.get('nosaukums')
        apraksts = request.form.get('apraksts')
        datums_str = request.form.get('datums')
        tips = request.form.get('tips')
        
        try:
            datums = datetime.fromisoformat(datums_str)
            notikums = Notikumi(nosaukums=nosaukums, apraksts=apraksts, datums=datums, tips=tips)
            db.session.add(notikums)
            db.session.commit()
            flash("Notikums pievienots!", "success")
            return redirect(url_for('admin_Notikumi'))
        except ValueError:
            flash("Nepareizs datums.", "danger")
    
    notikumi = Notikumi.query.order_by(Notikumi.datums.asc()).all()
    return render_template('admin_Notikumi.html', Notikumi=notikumi)

@app.route('/admin/notikums/<int:notikuma_id>/dzest', methods=['POST'])
def dzest_notikums(notikuma_id):
    if session.get('loma') != 'Administrators':
        flash("Jums nav atļaujas to darīt.", "danger")
        return redirect(url_for('index'))
    
    notikums = Notikumi.query.get_or_404(notikuma_id)
    db.session.delete(notikums)
    db.session.commit()
    flash("Notikums dzēsts!", "success")
    return redirect(url_for('admin_Notikumi'))

@app.context_processor
def inject_common():
    return {
        'ir_piesledzis': 'lietotajvards' in session,
        'current_year': datetime.utcnow().year
    }

if __name__ == "__main__":
    with app.app_context():
        print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print(f"Database file path: {db_path}")
        db.create_all()
    app.run(debug=True)