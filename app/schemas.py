from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class SubjectCreate(BaseModel):
    code: str
    name: str
    geofence_latitude: Optional[float] = None
    geofence_longitude: Optional[float] = None
    geofence_radius_meters: Optional[float] = None


class SubjectOut(BaseModel):
    id: int
    code: str
    name: str

    class Config:
        from_attributes = True


class LectureCreate(BaseModel):
    subject_id: int
    title: str
    scheduled_start: datetime
    scheduled_end: datetime
    location_latitude: Optional[float] = None
    location_longitude: Optional[float] = None
    location_radius_meters: Optional[float] = None


class AttendanceMarkRequest(BaseModel):
    lecture_id: int
    qr_token: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    device_hash: Optional[str] = Field(None, description="Stable hash for device binding")


class AttendanceOut(BaseModel):
    lecture_id: int
    student_id: int
    marked_at: datetime

    class Config:
        from_attributes = True