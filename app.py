from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///muschats.db'
db = SQLAlchemy(app)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    surname = db.Column(db.String(80), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # student, teacher, admin
    approved = db.Column(db.Boolean, default=False)


class Discussion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    likes = db.relationship('Like', backref='discussion', lazy=True)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    discussion_id = db.Column(db.Integer, db.ForeignKey('discussion.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    likes = db.relationship('Like', backref='comment', lazy=True)


class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    discussion_id = db.Column(db.Integer, db.ForeignKey('discussion.id'), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)


@app.route('/')
def home():
    discussions = Discussion.query.all()
    return render_template('home.html', discussions=discussions)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        name = request.form['name']
        surname = request.form['surname']
        role = request.form['role']
        user = User(username=username, password=password, name=name, surname=surname, role=role)
        db.session.add(user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password) and user.approved:
            session['user_id'] = user.id
            return redirect(url_for('home'))
    return render_template('login.html')


@app.route('/pievienot_disk', methods=['GET', 'POST'])
def create_discussion():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        discussion = Discussion(title=title, content=content, user_id=session['user_id'])
        db.session.add(discussion)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('create_discussion.html')


@app.route('/diskusija/<int:id>', methods=['GET', 'POST'])
def discussion(id):
    discussion = Discussion.query.get_or_404(id)
    comments = Comment.query.filter_by(discussion_id=id).all()
    if request.method == 'POST' and 'user_id' in session:
        content = request.form['content']
        comment = Comment(content=content, discussion_id=id, user_id=session['user_id'])
        db.session.add(comment)
        db.session.commit()
        return redirect(url_for('discussion', id=id))
    return render_template('discussion.html', discussion=discussion, comments=comments)


@app.route('/like/<type>/<int:id>')
def like(type, id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if type == 'discussion':
        like = Like(user_id=session['user_id'], discussion_id=id)
    elif type == 'comment':
        like = Like(user_id=session['user_id'], comment_id=id)
    db.session.add(like)
    db.session.commit()
    return redirect(request.referrer)


@app.route('/approve_users')
def approve_users():
    users = User.query.filter_by(approved=False).all()
    for user in users:
        user.approved = True
    db.session.commit()
    return redirect(url_for('home'))


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)





