from flask import Flask, request, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

basedir = os.path.abspath(os.path.dirname(__file__))
instance_folder = os.path.join(basedir, 'instance')
os.makedirs(instance_folder, exist_ok=True)
db_path = os.path.join(instance_folder, 'datubaze.db')
# Convert backslashes to forward slashes for SQLite URI
db_path_uri = db_path.replace('\\', '/')

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path_uri}'
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

class Diskusijas(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    virsraksts = db.Column(db.String(200), nullable=False)
    saturs = db.Column(db.Text, nullable=False)
    lietotaja_id = db.Column(db.Integer, db.ForeignKey('lietotaji.id'), nullable=False)
    datums = db.Column(db.DateTime, default=datetime.utcnow)
    komentari = db.relationship('Komentari', backref='diskusija', lazy=True, cascade='all, delete-orphan')

class Komentari(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    saturs = db.Column(db.Text, nullable=False)
    lietotaja_id = db.Column(db.Integer, db.ForeignKey('lietotaji.id'), nullable=False)
    diskusijas_id = db.Column(db.Integer, db.ForeignKey('diskusijas.id'), nullable=False)
    datums = db.Column(db.DateTime, default=datetime.utcnow)
    lietotajs = db.relationship('Lietotaji', backref='komentari')

class Patikumi(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    skaits = db.Column(db.Integer, default=0)

def get_patikumi():
    patikums = Patikumi.query.first()
    if not patikums:
        patikums = Patikumi(skaits=0)
        db.session.add(patikums)
        db.session.commit()
    return patikums

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
        if Lietotaji.query.filter_by(lietotajvards=lietotajvards).first():
            return "Lietotājvārds jau pastāv", 400
        hashed_password = generate_password_hash(parole)
        jauns_lietotajs = Lietotaji(lietotajvards=lietotajvards, parole=hashed_password, vards=vards, uzvards=uzvards, loma=loma)
        db.session.add(jauns_lietotajs)
        db.session.commit()
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        lietotajvards = request.form.get("lietotajvards")
        parole = request.form.get("parole")
        lietotajs = Lietotaji.query.filter_by(lietotajvards=lietotajvards).first()
        if lietotajs and check_password_hash(lietotajs.parole, parole):
            session['lietotajvards'] = lietotajvards
            session['lietotaja_id'] = lietotajs.id
            return redirect(url_for("index"))
        return "Nepareizs lietotājvārds vai parole", 401
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
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

@app.route("/patikt")
def patikt():
    if 'lietotajvards' not in session:
        return redirect(url_for("login"))
    patikums = get_patikumi()
    patikums.skaits += 1
    db.session.commit()
    return redirect(url_for("index"))

if __name__ == "__main__":
    with app.app_context():
        print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print(f"Database file path: {db_path}")
        db.create_all()
        
        # Check what tables were created
        insp = inspect(db.engine)
        tables = insp.get_table_names()
        print(f"Tables in database: {tables}")
        
        # Ensure Patikumi table has at least one entry
        if Patikumi.query.count() == 0:
            patikums = Patikumi(skaits=0)
            db.session.add(patikums)
            db.session.commit()
            print("Created Patikumi entry")
        print("Database initialized successfully")
    app.run(debug=True)