from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import os
from dotenv import load_dotenv

from .database import Base, engine
from .routers import auth as auth_router
from .routers import teacher as teacher_router
from .routers import student as student_router

load_dotenv()

app = FastAPI(title="QR Attendance System")
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET", "change_me_session_secret"))

app.include_router(auth_router.router)
app.include_router(teacher_router.router)
app.include_router(student_router.router)


@app.on_event("startup")
async def startup():
    Base.metadata.create_all(bind=engine)


@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <html>
      <head>
        <title>QR Attendance System</title>
        <style>
          body { font-family: system-ui, sans-serif; margin:40px; }
          .wrap { max-width: 800px; margin: auto; }
          .card { border: 1px solid #ddd; border-radius: 10px; padding: 16px; margin-bottom: 16px; }
        </style>
      </head>
      <body>
        <div class="wrap">
          <h1>QR Attendance System</h1>
          <div class="card">
            <h2>Teacher Quick Actions</h2>
            <ul>
              <li>POST /auth/signup (role=teacher)</li>
              <li>POST /auth/login</li>
              <li>POST /teacher/subjects</li>
              <li>POST /teacher/lectures</li>
              <li>POST /teacher/lectures/{lecture_id}/activate</li>
              <li>GET /teacher/lectures/{lecture_id}/qr</li>
              <li>GET /teacher/lectures/{lecture_id}/export.xlsx</li>
              <li>GET /teacher/subjects/{subject_id}/report</li>
            </ul>
          </div>
          <div class="card">
            <h2>Student Quick Actions</h2>
            <ul>
              <li>POST /auth/signup (role=student)</li>
              <li>POST /auth/login</li>
              <li>GET /student/scan</li>
              <li>POST /student/mark-attendance</li>
              <li>GET /student/my-attendance/{subject_id}</li>
              <li>GET /student/subjects/{subject_id}/report</li>
            </ul>
          </div>
        </div>
      </body>
    </html>
    """