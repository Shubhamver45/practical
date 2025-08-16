from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session

from ..auth import require_role
from ..database import get_db
from ..models import Subject, Lecture, Attendance, User
from ..schemas import SubjectCreate, LectureCreate
from ..utils import generate_qr_token
from openpyxl import Workbook

router = APIRouter(prefix="/teacher", tags=["teacher"]) 


@router.post("/subjects")
async def create_subject(payload: SubjectCreate, db: Session = Depends(get_db), user=Depends(require_role("teacher"))):
    if db.query(Subject).filter(Subject.code == payload.code).first():
        raise HTTPException(status_code=400, detail="Subject code already exists")
    subject = Subject(
        code=payload.code,
        name=payload.name,
        teacher_id=user.id,
        geofence_latitude=payload.geofence_latitude,
        geofence_longitude=payload.geofence_longitude,
        geofence_radius_meters=payload.geofence_radius_meters,
    )
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return {"id": subject.id, "code": subject.code, "name": subject.name}


@router.post("/lectures")
async def create_lecture(payload: LectureCreate, db: Session = Depends(get_db), user=Depends(require_role("teacher"))):
    subject = db.get(Subject, payload.subject_id)
    if not subject or subject.teacher_id != user.id:
        raise HTTPException(status_code=404, detail="Subject not found")
    lecture = Lecture(
        subject_id=payload.subject_id,
        title=payload.title,
        scheduled_start=payload.scheduled_start,
        scheduled_end=payload.scheduled_end,
        is_active=False,
        location_latitude=payload.location_latitude,
        location_longitude=payload.location_longitude,
        location_radius_meters=payload.location_radius_meters,
    )
    db.add(lecture)
    db.commit()
    db.refresh(lecture)
    return {"id": lecture.id, "title": lecture.title}


@router.post("/lectures/{lecture_id}/activate")
async def activate_lecture(lecture_id: int, db: Session = Depends(get_db), user=Depends(require_role("teacher"))):
    lecture = db.get(Lecture, lecture_id)
    if not lecture or lecture.subject.teacher_id != user.id:
        raise HTTPException(status_code=404, detail="Lecture not found")
    lecture.is_active = True
    db.commit()
    return {"message": "Lecture activated"}


@router.get("/lectures/{lecture_id}/qr", response_class=HTMLResponse)
async def lecture_qr_page(lecture_id: int, db: Session = Depends(get_db), user=Depends(require_role("teacher"))):
    lecture = db.get(Lecture, lecture_id)
    if not lecture or lecture.subject.teacher_id != user.id:
        raise HTTPException(status_code=404, detail="Lecture not found")
    # Simple HTML page that reloads token every 30s
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset=\"utf-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
      <title>Lecture QR</title>
      <style>
        body {{ font-family: system-ui, sans-serif; background: #0b1021; color: #f2f5ff; display:flex; align-items:center; justify-content:center; height:100vh; margin:0; }}
        .card {{ background:#121838; padding:24px; border-radius:16px; text-align:center; box-shadow: 0 10px 30px rgba(0,0,0,0.4); }}
        .token {{ font-family: monospace; font-size: 18px; margin-top: 12px; opacity: 0.8; }}
        canvas {{ background:#fff; padding:12px; border-radius:8px; }}
      </style>
    </head>
    <body>
      <div class=\"card\">
        <h2>{lecture.subject.code} - {lecture.title}</h2>
        <div id=\"qrcode\"></div>
        <div class=\"token\" id=\"token\"></div>
        <p>Token rotates every 30 seconds</p>
      </div>
      <script src=\"https://cdn.jsdelivr.net/npm/qrcode@1.5.3/build/qrcode.min.js\"></script>
      <script>
        const lectureId = {lecture.id};
        async function refreshToken() {{
          const res = await fetch(`/teacher/qr-token?lecture_id=${{lectureId}}`, {{ credentials: 'include' }});
          const data = await res.json();
          const token = data.token;
          document.getElementById('token').textContent = token;
          const msg = JSON.stringify({{ lecture_id: lectureId, token }});
          const container = document.getElementById('qrcode');
          container.innerHTML = '';
          QRCode.toCanvas(document.createElement('canvas'), msg, {{ width: 300 }}, function (err, canvas) {{
            if (!err) container.appendChild(canvas);
          }});
        }}
        refreshToken();
        setInterval(refreshToken, 30000);
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.get("/qr-token")
async def get_qr_token(lecture_id: int, db: Session = Depends(get_db), user=Depends(require_role("teacher"))):
    lecture = db.get(Lecture, lecture_id)
    if not lecture or lecture.subject.teacher_id != user.id:
        raise HTTPException(status_code=404, detail="Lecture not found")
    token = generate_qr_token(lecture_id)
    return {"token": token}


@router.get("/subjects/{subject_id}/report", response_class=HTMLResponse)
async def subject_report(subject_id: int, db: Session = Depends(get_db), user=Depends(require_role("teacher"))):
    subject = db.get(Subject, subject_id)
    if not subject or subject.teacher_id != user.id:
        raise HTTPException(status_code=404, detail="Subject not found")
    lectures = db.query(Lecture).filter(Lecture.subject_id == subject_id).all()
    total_lectures = len(lectures)
    # Attendance count per lecture
    attendance_counts = []
    labels = []
    for l in lectures:
        cnt = db.query(Attendance).filter(Attendance.lecture_id == l.id).count()
        attendance_counts.append(cnt)
        labels.append(l.title)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset=\"utf-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
      <title>Subject Report</title>
      <script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>
      <style>
        body {{ font-family: system-ui, sans-serif; margin: 24px; }}
        .wrap {{ max-width: 960px; margin:auto; }}
        .card {{ border:1px solid #ddd; border-radius:12px; padding:16px; margin-bottom:16px; }}
      </style>
    </head>
    <body>
      <div class=\"wrap\">
        <h2>{subject.code} - {subject.name} (Lectures: {total_lectures})</h2>
        <div class=\"card\">
          <canvas id=\"byLecture\" height=\"120\"></canvas>
        </div>
      </div>
      <script>
        const labels = {labels};
        const counts = {attendance_counts};
        new Chart(document.getElementById('byLecture'), {{
          type: 'bar',
          data: {{ labels, datasets: [{{ label: 'Attendance Count', data: counts, backgroundColor: '#4f46e5' }}] }},
          options: {{ responsive: true, maintainAspectRatio: false }}
        }});
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.get("/lectures/{lecture_id}/export.xlsx")
async def export_attendance(lecture_id: int, db: Session = Depends(get_db), user=Depends(require_role("teacher"))):
    lecture = db.get(Lecture, lecture_id)
    if not lecture or lecture.subject.teacher_id != user.id:
        raise HTTPException(status_code=404, detail="Lecture not found")

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance"
    ws.append(["Student ID", "Student Username", "Student Name", "Marked At", "Latitude", "Longitude", "Device Hash"])

    # Join attendance with user info
    rows = (
        db.query(Attendance, User)
        .join(User, User.id == Attendance.student_id)
        .filter(Attendance.lecture_id == lecture_id)
        .all()
    )

    for att, student in rows:
        ws.append([student.id, student.username, student.full_name, att.marked_at, att.latitude, att.longitude, att.device_hash])

    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    filename = f"attendance_lecture_{lecture_id}.xlsx"
    headers = {"Content-Disposition": f"attachment; filename={filename}"}
    return StreamingResponse(file_stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)