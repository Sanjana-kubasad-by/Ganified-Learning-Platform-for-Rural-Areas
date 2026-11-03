from app import app
from models import db, User, QuizQuestion, StudentProgress
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username='teacher').first():
        t = User(username='teacher', password=generate_password_hash('teachpass'), role='teacher')
        db.session.add(t)
    if not User.query.filter_by(username='student1').first():
        s = User(username='student1', password=generate_password_hash('studentpass'), role='student')
        db.session.add(s)
    db.session.commit()

    # sample questions: maths & english & gk
    if QuizQuestion.query.count() == 0:
        qs = [
            QuizQuestion(subject='maths', prompt='2 + 2 = ?', option_a='3', option_b='4', option_c='5', option_d='6', correct='B'),
            QuizQuestion(subject='english', prompt='Correct "technolgy" to?', option_a='technolgy', option_b='technology', option_c='technalogy', option_d='technoly', correct='B'),
            QuizQuestion(subject='gk', prompt='Capital of India?', option_a='Mumbai', option_b='New Delhi', option_c='Kolkata', option_d='Chennai', correct='B'),
        ]
        db.session.add_all(qs)
    db.session.commit()
    print("DB initialized and seeded.")
