from models import db, StudentProgress
def award_points(student_id, points):
    sp = StudentProgress.query.filter_by(student_id=student_id).first()
    if not sp:
        sp = StudentProgress(student_id=student_id, points=0, level=1)
        db.session.add(sp)
    sp.points += points
    # simple level up: every 100 points => level++
    new_level = 1 + sp.points // 100
    sp.level = new_level
    db.session.commit()
