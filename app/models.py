from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    Float,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # 'student' or 'teacher'
    device_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subjects_taught: Mapped[list["Subject"]] = relationship("Subject", back_populates="teacher")
    enrollments: Mapped[list["Enrollment"]] = relationship("Enrollment", back_populates="student")


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    # Default geofence for the subject (optional). Lectures can override.
    geofence_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geofence_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geofence_radius_meters: Mapped[float | None] = mapped_column(Float, nullable=True)

    teacher: Mapped["User"] = relationship("User", back_populates="subjects_taught")
    enrollments: Mapped[list["Enrollment"]] = relationship("Enrollment", back_populates="subject")
    lectures: Mapped[list["Lecture"]] = relationship("Lecture", back_populates="subject")


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (UniqueConstraint("student_id", "subject_id", name="uq_student_subject"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)

    student: Mapped["User"] = relationship("User", back_populates="enrollments")
    subject: Mapped["Subject"] = relationship("Subject", back_populates="enrollments")


class Lecture(Base):
    __tablename__ = "lectures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)

    scheduled_start: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    scheduled_end: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    location_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_radius_meters: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    subject: Mapped["Subject"] = relationship("Subject", back_populates="lectures")
    attendances: Mapped[list["Attendance"]] = relationship("Attendance", back_populates="lecture")


class Attendance(Base):
    __tablename__ = "attendances"
    __table_args__ = (UniqueConstraint("lecture_id", "student_id", name="uq_lecture_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lecture_id: Mapped[int] = mapped_column(ForeignKey("lectures.id"), nullable=False)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    marked_at: Mapped[str] = mapped_column(DateTime(timezone=True), server_default=func.now())

    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    device_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    lecture: Mapped["Lecture"] = relationship("Lecture", back_populates="attendances")