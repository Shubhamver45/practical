from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from ..auth import require_role
from ..database import get_db
from ..models import Lecture, Attendance, Enrollment, Subject, User
from ..schemas import AttendanceMarkRequest
from ..utils import is_valid_qr_token, haversine_distance_meters

router = APIRouter(prefix="/student", tags=["student"]) 


@router.get("/scan", response_class=HTMLResponse)
async def scan_page(user=Depends(require_role("student"))):
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset=\"utf-8\" />
        <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
        <title>Scan Attendance</title>
        <style>
            body { font-family: system-ui, sans-serif; padding: 20px; }
            .card { border:1px solid #ddd; border-radius:12px; padding:16px; max-width:600px; margin:auto; }
            .row { margin-bottom: 12px; }
            input, button { padding: 10px; font-size: 14px; }
            #out { white-space: pre-wrap; background:#f8f8f8; padding:10px; border-radius:8px; }
        </style>
    </head>
    <body>
        <div class=\"card\">
            <h2>Scan Attendance</h2>
            <div class=\"row\">Paste scanned QR payload here:</div>
            <textarea id=\"payload\" rows=\"4\" style=\"width:100%\"></textarea>
            <div class=\"row\">
              <label>Device hash (first time binds your device):</label>
              <input id=\"device\" placeholder=\"e.g. hashed-device-id\" style=\"width:100%\" />
            </div>
            <div class=\"row\">
              <button onclick=\"mark()\">Mark Attendance</button>
            </div>
            <div id=\"out\"></div>
        </div>
        <script>
          function getLocation() {
            return new Promise((resolve) => {
              if (!navigator.geolocation) return resolve(null);
              navigator.geolocation.getCurrentPosition((pos) => {
                resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude });
              }, () => resolve(null), { enableHighAccuracy: true, timeout: 8000 });
            });
          }
          async function mark() {
            const out = document.getElementById('out');
            out.textContent = 'Working...';
            let data;
            try { data = JSON.parse(document.getElementById('payload').value || '{}'); } catch (e) {
              out.textContent = 'Invalid QR payload JSON'; return; }
            const loc = await getLocation();
            const body = {
              lecture_id: data.lecture_id,
              qr_token: data.token,
              latitude: loc ? loc.lat : null,
              longitude: loc ? loc.lon : null,
              device_hash: document.getElementById('device').value || null,
            };
            const res = await fetch('/student/mark-attendance', {
              method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify(body)
            });
            const j = await res.json();
            out.textContent = JSON.stringify(j, null, 2);
          }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.get("/subjects/{subject_id}/report", response_class=HTMLResponse)
async def student_subject_report(subject_id: int, db: Session = Depends(get_db), user=Depends(require_role("student"))):
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")
    lectures = db.query(Lecture).filter(Lecture.subject_id == subject_id).all()
    attended_ids = set(r.lecture_id for r in db.query(Attendance).filter(Attendance.student_id == user.id, Attendance.lecture_id.in_([l.id for l in lectures])).all())
    total = len(lectures)
    present = len(attended_ids)
    absent = total - present
    percent = (present / total * 100.0) if total else 0.0

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset=\"utf-8\" />
      <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
      <title>My Attendance Report</title>
      <script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>
      <style>
        body {{ font-family: system-ui, sans-serif; margin: 24px; }}
        .wrap {{ max-width: 720px; margin:auto; }}
        .card {{ border:1px solid #ddd; border-radius:12px; padding:16px; margin-bottom:16px; }}
      </style>
    </head>
    <body>
      <div class=\"wrap\">
        <h2>{subject.code} - {subject.name}</h2>
        <p>Total lectures: {total} | Present: {present} | Absent: {absent} | Percentage: {percent:.1f}%</p>
        <div class=\"card\">
          <canvas id=\"pie\" height=\"120\"></canvas>
        </div>
      </div>
      <script>
        new Chart(document.getElementById('pie'), {{
          type: 'pie',
          data: {{ labels: ['Present', 'Absent'], datasets: [{{ data: [{present}, {absent}], backgroundColor: ['#10b981','#ef4444'] }}] }},
        }});
      </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@router.post("/mark-attendance")
async def mark_attendance(payload: AttendanceMarkRequest, db: Session = Depends(get_db), user=Depends(require_role("student"))):
    lecture = db.get(Lecture, payload.lecture_id)
    if not lecture or not lecture.is_active:
        raise HTTPException(status_code=400, detail="Lecture is not active or does not exist")

    # Check enrollment
    enrollment = db.query(Enrollment).filter(Enrollment.student_id == user.id, Enrollment.subject_id == lecture.subject_id).first()
    if not enrollment:
        raise HTTPException(status_code=403, detail="Not enrolled in subject")

    # Validate QR token
    if not is_valid_qr_token(payload.qr_token, lecture.id):
        raise HTTPException(status_code=400, detail="Invalid or expired QR token")

    # Enforce one-device binding: first successful mark binds device_hash into User
    if user.device_hash is None and payload.device_hash:
        user.device_hash = payload.device_hash
        db.add(user)
        db.commit()
        db.refresh(user)

    # If already bound, ensure same device
    if user.device_hash is not None:
        if not payload.device_hash or payload.device_hash != user.device_hash:
            raise HTTPException(status_code=403, detail="Different device not allowed")

    # Geofence: use lecture location if set; otherwise subject default if set. If neither set, no geofence enforced.
    target_lat = lecture.location_latitude or lecture.subject.geofence_latitude
    target_lon = lecture.location_longitude or lecture.subject.geofence_longitude
    radius = lecture.location_radius_meters or lecture.subject.geofence_radius_meters

    if target_lat is not None and target_lon is not None and radius is not None:
        if payload.latitude is None or payload.longitude is None:
            raise HTTPException(status_code=400, detail="Location required for geofenced attendance")
        distance = haversine_distance_meters(payload.latitude, payload.longitude, target_lat, target_lon)
        if distance > radius:
            raise HTTPException(status_code=403, detail="You are outside the allowed area")

    # Save attendance (unique per lecture per student)
    existing = db.query(Attendance).filter(Attendance.lecture_id == lecture.id, Attendance.student_id == user.id).first()
    if existing:
        return {"message": "Attendance already marked"}

    att = Attendance(
        lecture_id=lecture.id,
        student_id=user.id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        device_hash=payload.device_hash,
    )
    db.add(att)
    db.commit()
    return {"message": "Attendance marked"}


@router.get("/my-attendance/{subject_id}")
async def my_attendance(subject_id: int, db: Session = Depends(get_db), user=Depends(require_role("student"))):
    # Return monthly breakdown for a subject
    subject = db.get(Subject, subject_id)
    if not subject:
        raise HTTPException(status_code=404, detail="Subject not found")

    # Gather all lectures for subject and whether attended
    lectures = db.query(Lecture).filter(Lecture.subject_id == subject_id).all()
    attended_ids = set(r.lecture_id for r in db.query(Attendance).filter(Attendance.student_id == user.id, Attendance.lecture_id.in_([l.id for l in lectures])).all())

    result = []
    for l in lectures:
        result.append({
            "lecture_id": l.id,
            "title": l.title,
            "date": l.scheduled_start.isoformat() if hasattr(l.scheduled_start, 'isoformat') else str(l.scheduled_start),
            "attended": l.id in attended_ids,
        })

    # Basic aggregates
    total = len(lectures)
    present = len(attended_ids)
    percent = (present / total * 100.0) if total else 0.0

    return {"subject": {"id": subject.id, "code": subject.code, "name": subject.name}, "summary": {"total": total, "present": present, "percent": percent}, "lectures": result}