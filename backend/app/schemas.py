from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

class Profile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    name: str = ""
    skills: List[str] = Field(default_factory=list, max_length=100)
    experience: List[str] = Field(default_factory=list, max_length=50)
    education: List[str] = Field(default_factory=list, max_length=30)
    projects: List[str] = Field(default_factory=list, max_length=50)
    certifications: List[str] = Field(default_factory=list, max_length=50)
    location: str = Field(default="", max_length=160)
    career_level: str = Field(default="Entry", max_length=40)

class ProfilePayload(BaseModel):
    profile: Profile

class JobTargetPayload(ProfilePayload):
    job_id: int

class InterviewStartPayload(ProfilePayload):
    job_title: str = Field(min_length=1, max_length=160)
    job_id: Optional[int] = None
    previous: List[str] = Field(default_factory=list, max_length=30)

class InterviewEvalPayload(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=12000)
    job_title: str = Field(min_length=1, max_length=160)
    session_id: Optional[int] = None
