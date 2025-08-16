from datetime import datetime, timedelta, timezone

from .database import Base, engine, SessionLocal
from .models import User, Subject, Enrollment, Lecture
from .auth import hash_password


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Create teacher and student if not exists
        teacher = db.query(User).filter_by(username="teacher1").first()
        if not teacher:
            teacher = User(username="teacher1", password_hash=hash_password("pass"), full_name="Teacher One", role="teacher")
            db.add(teacher)
            db.commit()
            db.refresh(teacher)
        student = db.query(User).filter_by(username="student1").first()
        if not student:
            student = User(username="student1", password_hash=hash_password("pass"), full_name="Student One", role="student")
            db.add(student)
            db.commit()
            db.refresh(student)

        subject = db.query(Subject).filter_by(code="CS101").first()
        if not subject:
            subject = Subject(code="CS101", name="Intro to CS", teacher_id=teacher.id, geofence_latitude=19.076, geofence_longitude=72.8777, geofence_radius_meters=300)
            db.add(subject)
            db.commit()
            db.refresh(subject)

        enroll = db.query(Enrollment).filter_by(student_id=student.id, subject_id=subject.id).first()
        if not enroll:
            enroll = Enrollment(student_id=student.id, subject_id=subject.id)
            db.add(enroll)
            db.commit()

        now = datetime.now(timezone.utc)
        lect = db.query(Lecture).filter_by(subject_id=subject.id, title="Week 1").first()
        if not lect:
            lect = Lecture(subject_id=subject.id, title="Week 1", scheduled_start=now - timedelta(minutes=30), scheduled_end=now + timedelta(minutes=30), is_active=True)
            db.add(lect)
            db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    seed()