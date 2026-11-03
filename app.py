from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import random
import os

# ====================
# APP CONFIG
# ====================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-secret-key'  # change this in production
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///gamified_learning.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ====================
# MODELS
# ====================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'student' or 'teacher'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class QuizQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(50), nullable=False)
    prompt = db.Column(db.String(500), nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    correct = db.Column(db.String(1), nullable=False)

class Attempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('quiz_question.id'), nullable=False)
    chosen = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)
    points = db.Column(db.Integer, nullable=False)
    time_taken = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

class StudentProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    points = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)

# ====================
# LOGIN MANAGER
# ====================
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ====================
# HELPER FUNCTION
# ====================
def award_points(student_id, points):
    progress = StudentProgress.query.filter_by(student_id=student_id).first()
    if not progress:
        progress = StudentProgress(student_id=student_id, points=points, level=1)
        db.session.add(progress)
    else:
        progress.points += points
        progress.level = (progress.points // 50) + 1  # every 50 pts = level up
    db.session.commit()

# ====================
# ROUTES
# ====================
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        u = request.form['username'].strip()
        p = request.form['password']
        role = request.form['role']
        if User.query.filter_by(username=u).first():
            flash('Username already exists', 'warning')
        else:
            user = User(username=u, password=generate_password_hash(p), role=role)
            db.session.add(user)
            db.session.commit()
            flash('Registered! Log in now.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        u = request.form['username']
        p = request.form['password']
        user = User.query.filter_by(username=u).first()
        if user and check_password_hash(user.password, p):
            login_user(user)
            if user.role == 'student':
                return redirect(url_for('student_dashboard'))
            else:
                return redirect(url_for('teacher_report'))
        else:
            flash('Invalid credentials', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/student')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        return "Forbidden", 403
    progress = StudentProgress.query.filter_by(student_id=current_user.id).first()
    if not progress:
        progress = StudentProgress(student_id=current_user.id, points=0, level=1)
        db.session.add(progress)
        db.session.commit()
    return render_template('student_dashboard.html', progress=progress)

@app.route('/quiz/<subject>')
@login_required
def quiz(subject):
    if current_user.role != 'student':
        return "Forbidden", 403
    qs = QuizQuestion.query.filter_by(subject=subject).all()
    chosen = random.sample(qs, min(5, len(qs)))
    qlist = [{
        'id': q.id,
        'prompt': q.prompt,
        'A': q.option_a,
        'B': q.option_b,
        'C': q.option_c,
        'D': q.option_d
    } for q in chosen]
    return render_template('quiz.html', questions=qlist, subject=subject)

@app.route('/submit_answer', methods=['POST'])
@login_required
def submit_answer():
    if current_user.role != 'student':
        return jsonify({'error':'forbidden'}), 403
    data = request.json
    qid = data.get('question_id')
    chosen = data.get('chosen')
    time_taken = float(data.get('time_taken', 0))
    q = QuizQuestion.query.get(qid)
    if not q:
        return jsonify({'error':'no question'}), 400
    is_correct = (chosen == q.correct)
    points = 10 if is_correct else 0
    if is_correct and time_taken < 10:
        points += 5
    att = Attempt(student_id=current_user.id, question_id=qid, chosen=chosen,
                  is_correct=is_correct, points=points, time_taken=time_taken)
    db.session.add(att)
    db.session.commit()
    if points > 0:
        award_points(current_user.id, points)
    return jsonify({'is_correct':is_correct, 'points':points})

@app.route('/leaderboard')
@login_required
def leaderboard():
    tops = (
        db.session.query(User.username, StudentProgress.points, StudentProgress.level)
        .join(StudentProgress, StudentProgress.student_id == User.id)
        .order_by(StudentProgress.points.desc())
        .limit(20)
        .all()
    )
    return render_template('leaderboard.html', tops=tops)

@app.route('/teacher')
@login_required
def teacher_report():
    if current_user.role != 'teacher':
        return "Forbidden", 403
    students = User.query.filter_by(role='student').all()
    student_stats = []
    for s in students:
        total_attempts = Attempt.query.filter_by(student_id=s.id).count()
        correct_count = Attempt.query.filter_by(student_id=s.id, is_correct=True).count()
        progress = StudentProgress.query.filter_by(student_id=s.id).first()
        student_stats.append({
            'username': s.username,
            'attempts': total_attempts,
            'correct': correct_count,
            'points': progress.points if progress else 0
        })
    return render_template('teacher_report.html', students=student_stats)

@app.route('/add_question', methods=['GET','POST'])
@login_required
def add_question():
    if current_user.role != 'teacher':
        return "Forbidden", 403
    if request.method=='POST':
        q = QuizQuestion(
            subject=request.form['subject'],
            prompt=request.form['prompt'],
            option_a=request.form['a'],
            option_b=request.form['b'],
            option_c=request.form['c'],
            option_d=request.form['d'],
            correct=request.form['correct']
        )
        db.session.add(q)
        db.session.commit()
        flash('Question added', 'success')
        return redirect(url_for('add_question'))
    return render_template('add_question.html')

# ====================
# DATABASE SEEDING
# ====================
def seed_questions():
    if QuizQuestion.query.count() > 0:
        return  # already seeded

    data = {
        "maths": [
            ("What is 15 × 3?", "35", "45", "55", "60", "B"),
            ("Square root of 81?", "9", "8", "6", "7", "A"),
            ("Angles 90°,45°,45° → ?", "Equilateral", "Scalene", "Isosceles right triangle", "Obtuse", "C"),
            ("Perimeter of a square (side=8)?", "32 cm", "16 cm", "64 cm", "20 cm", "A"),
            ("Simplify: (6 + 3) × 2", "12", "14", "16", "18", "D")
        ],
        "english": [
            ("Correct spelling?", "Recieve", "Receive", "Receeve", "Receve", "B"),
            ("Synonym of 'Happy'?", "Sad", "Angry", "Joyful", "Tired", "C"),
            ("Adjective in 'The sky is blue'?", "Sky", "Is", "Blue", "The", "C"),
            ("Proper noun?", "river", "city", "Ganga", "lake", "C"),
            ("Choose correct article: ___ apple", "a", "an", "the", "none", "B")
        ],
        "gk": [
            ("Who is the father of our nation (India)?", "Mahatma Gandhi", "Nehru", "Patel", "Ambedkar", "A"),
            ("Largest ocean?", "Indian", "Pacific", "Atlantic", "Arctic", "B"),
            ("Fastest land animal?", "Cheetah", "Tiger", "Lion", "Horse", "A"),
            ("Which planet is known as Red Planet?", "Earth", "Mars", "Venus", "Jupiter", "B"),
            ("National animal of India?", "Peacock", "Lion", "Tiger", "Elephant", "C")
        ]
    }

    for subject, questions in data.items():
        for q in questions:
            db.session.add(QuizQuestion(subject=subject, prompt=q[0],
                                        option_a=q[1], option_b=q[2],
                                        option_c=q[3], option_d=q[4], correct=q[5]))
    db.session.commit()

# ====================
# MAIN
# ====================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_questions()
    app.run(debug=True)
