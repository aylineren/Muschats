from flask import Flask, request, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///datubaze.db'
app.config['SECRET_KEY'] = '555555'
db = SQLAlchemy(app)

class Lietotaji(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lietotajvards = db.Column(db.String(80), unique=True, nullable=False)
    parole = db.Column(db.String(20), nullable=False)
    vards = db.Column(db.String(80), nullable=False)
    uzvards = db.Column(db.String(80), nullable=False)
    loma = db.Column(db.String(80), nullable=False)

@app.route("/")
def index():
    discussions = []
    return render_template("index.html", discussions=discussions)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        lietotajvards = request.form.get("lietotajvards")
        parole = request.form.get("parole")[:20]
        vards = request.form.get("vards")
        uzvards = request.form.get("uzvards")
        loma = request.form.get("loma")
        if Lietotaji.query.filter_by(lietotajvards=lietotajvards).first():
            return "Lietotājvārds jau pastāv", 400
        jauns_lietotajs = Lietotaji(lietotajvards=lietotajvards, parole=parole, vards=vards, uzvards=uzvards, loma=loma)
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
        if lietotajs and lietotajs.parole == parole:
            return redirect(url_for("index"))
        return "Nepareizs lietotājvārds vai parole", 401
    return render_template("login.html")

if __name__ == "__main__":
    app.run()