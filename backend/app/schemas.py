from pydantic import BaseModel
from typing import List

class Profile(BaseModel):
    skills: List[str] = []
    experience: List[str] = []
    education: List[str] = []
    projects: List[str] = []
    certifications: List[str] = []
    location: str = ""
    career_level: str = "Entry"

class ProfilePayload(BaseModel):
    profile: Profile

class JobTargetPayload(BaseModel):
    profile: Profile
    job_id: int

class InterviewStartPayload(BaseModel):
    profile: Profile
    job_title: str

class InterviewEvalPayload(BaseModel):
    question: str
    answer: str
    job_title: str