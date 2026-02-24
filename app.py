from flask import Flask, request, render_template, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os

basedir = os.path.abspath(os.path.dirname(__file__))
instance_folder = os.path.join(basedir, 'instance')
os.makedirs(instance_folder, exist_ok=True)
db_path = os.path.join(instance_folder, 'datubaze.db')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = '555555' 
db = SQLAlchemy(app)

class Lietotaji(db.Model):
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

class Diskusijas(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    virsraksts = db.Column(db.String(200), nullable=False)
    saturs = db.Column(db.Text, nullable=False)
    lietotaja_id = db.Column(db.Integer, db.ForeignKey('lietotaji.id'), nullable=False)
    datums = db.Column(db.DateTime, default=datetime.utcnow)
    ir_redigets = db.Column(db.Boolean, default=False)
    redigets_datums = db.Column(db.DateTime, nullable=True)
    komentari = db.relationship('Komentari', backref='diskusija', lazy=True, cascade='all, delete-orphan')
    lietotajs = db.relationship('Lietotaji', backref='diskusijas')

class Komentari(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    saturs = db.Column(db.Text, nullable=False)
    lietotaja_id = db.Column(db.Integer, db.ForeignKey('lietotaji.id'), nullable=False)
    diskusijas_id = db.Column(db.Integer, db.ForeignKey('diskusijas.id'), nullable=False)
    datums = db.Column(db.DateTime, default=datetime.utcnow)
    ir_redigets = db.Column(db.Boolean, default=False)
    redigets_datums = db.Column(db.DateTime, nullable=True)
    lietotajs = db.relationship('Lietotaji', backref='komentari')

class Patikumi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    skaits = db.Column(db.Integer, default=0)

class patikumi_lietotajs(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lietotaja_id = db.Column(db.Integer, db.ForeignKey('lietotaji.id'), unique=True, nullable=False)

UPLOAD_FOLDER = os.path.join(basedir, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT

@app.route("/")
def index():
    patikums = get_patikumi()
    diskusijas = Diskusijas.query.order_by(Diskusijas.datums.desc()).all()
    return render_template("index.html", diskusijas=diskusijas, patikumi=patikums.skaits, ir_piesledzis='lietotajvards' in session)

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
        jauns_lietotajs = Lietotaji(lietotajvards=lietotajvards, parole=hashed_password, vards=vards, uzvards=uzvards, loma=loma, epasts=epasts, ir_apstiprinats=ir_apstiprinats)
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
    if request.method == "POST":
        virsraksts = request.form.get("virsraksts")
        saturs = request.form.get("saturs")
        jauna = Diskusijas(virsraksts=virsraksts, saturs=saturs, lietotaja_id=session['lietotaja_id'])
        db.session.add(jauna)
        db.session.commit()
        return redirect(url_for("index"))
    return render_template("jauna_diskusija.html")

@app.route("/diskusijas/<int:diskusijas_id>", methods=["GET", "POST"])
def diskusija(diskusijas_id):
    diskusija = Diskusijas.query.get_or_404(diskusijas_id)
    if request.method == "POST":
        if 'lietotajvards' not in session:
            return redirect(url_for("login"))
        saturs = request.form.get("saturs")
        komentars = Komentari(saturs=saturs, lietotaja_id=session['lietotaja_id'], diskusijas_id=diskusijas_id)
        db.session.add(komentars)
        db.session.commit()
        return redirect(url_for("diskusija", diskusijas_id=diskusijas_id))
    return render_template("diskusija.html", diskusija=diskusija, ir_piesledzis='lietotajvards' in session)

def get_patikumi():
    patikums = Patikumi.query.first()
    if not patikums:
        patikums = Patikumi(skaits=0)
        db.session.add(patikums)
        db.session.commit()
    count = patikumi_lietotajs.query.count()
    if patikums.skaits != count:
        patikums.skaits = count
        db.session.commit()
    return patikums

@app.route("/patikt")
def patikt():
    if 'lietotajvards' not in session:
        return redirect(url_for("login"))
    lietotajs_id = session.get('lietotaja_id')
    if patikumi_lietotajs.query.filter_by(lietotaja_id=lietotajs_id).first():
        flash("Tu jau esi šeit atstājis atzīmi 'Patīk'.")
        return redirect(url_for("index"))
    pu = patikumi_lietotajs(lietotaja_id=lietotajs_id)
    db.session.add(pu)
    db.session.commit()
    patikums = get_patikumi()
    patikums.skaits = patikumi_lietotajs.query.count()
    db.session.commit()
    return redirect(url_for("index"))


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
    return render_template('profils.html', lietotajs=lietotajs)


@app.route('/diskusijas/<int:diskusijas_id>/rediget', methods=['GET', 'POST'])
def rediget_diskusija(diskusijas_id):
    diskusija = Diskusijas.query.get_or_404(diskusijas_id)
    if diskusija.lietotaja_id != session.get('lietotaja_id'):
        flash("Jums nav atļaujas to rediģēt.", "danger")
        return redirect(url_for('diskusija', diskusijas_id=diskusijas_id))
    if request.method == 'POST':
        diskusija.virsraksts = request.form.get('virsraksts')
        diskusija.saturs = request.form.get('saturs')
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


@app.route('/komentari/<int:komentara_id>/rediget', methods=['GET', 'POST'])
def rediget_komentars(komentara_id):
    komentars = Komentari.query.get_or_404(komentara_id)
    if komentars.lietotaja_id != session.get('lietotaja_id'):
        flash("Jums nav atļaujas to rediģēt.", "danger")
        return redirect(url_for('diskusija', diskusijas_id=komentars.diskusijas_id))
    if request.method == 'POST':
        komentars.saturs = request.form.get('saturs')
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


@app.route('/admin/panel')
def admin_panel():
    if session.get('loma') != 'Administrators':
        flash("Jums nav piekļuves šim lapai.", "danger")
        return redirect(url_for('index'))
    neapstiprinats_lietotajss = Lietotaji.query.filter_by(ir_apstiprinats=False).all()
    all_lietotajss = Lietotaji.query.all()
    return render_template('admin_panel.html', neapstiprinats_lietotajss=neapstiprinats_lietotajss, all_lietotajss=all_lietotajss)


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
    app.run(debug=True)