"""Database operations for the single-user local MVP."""
import json
from sqlalchemy import select, desc
from app.models import Base, SessionLocal, engine, User, ProfileRecord, JobRecord, MatchRecord, LearningPlanRecord, InterviewSession

def init_db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.get(User, 1) is None:
            db.add(User(id=1, email="local@careerflow.invalid")); db.commit()

def save_profile(profile):
    payload = profile.model_dump() if hasattr(profile, "model_dump") else profile
    with SessionLocal() as db:
        row = db.scalar(select(ProfileRecord).where(ProfileRecord.user_id == 1))
        if row is None: row = ProfileRecord(user_id=1, payload=json.dumps(payload)); db.add(row)
        else: row.payload=json.dumps(payload)
        db.commit()
    return payload

def get_profile():
    with SessionLocal() as db:
        row=db.scalar(select(ProfileRecord).where(ProfileRecord.user_id==1))
        return json.loads(row.payload) if row else None

def seed_jobs(jobs):
    with SessionLocal() as db:
        for job in jobs:
            row=db.get(JobRecord,job["id"])
            values={"title":job["title"],"company":job["company"],"location":job["location"],"payload":json.dumps(job)}
            if row is None: db.add(JobRecord(id=job["id"],**values))
            else:
                for key,value in values.items(): setattr(row,key,value)
        db.commit()

def save_plan(job_id, plan):
    with SessionLocal() as db:
        row=LearningPlanRecord(job_id=job_id,payload=json.dumps(plan));db.add(row);db.commit();db.refresh(row);return row.id

def save_match(job_id, score, payload):
    with SessionLocal() as db:
        db.add(MatchRecord(job_id=job_id,score=score,payload=json.dumps(payload)));db.commit()

def create_interview(job_title, question):
    with SessionLocal() as db:
        row=InterviewSession(job_title=job_title,question=question);db.add(row);db.commit();db.refresh(row);return row.id

def evaluate_interview(session_id, answer, evaluation):
    with SessionLocal() as db:
        row=db.get(InterviewSession,session_id) if session_id else None
        if row is None:
            row=InterviewSession(job_title="Practice",question="",answer=answer,evaluation=json.dumps(evaluation));db.add(row)
        else: row.answer=answer;row.evaluation=json.dumps(evaluation)
        db.commit();db.refresh(row);return row.id

def interview_history(limit=20):
    with SessionLocal() as db:
        rows=db.scalars(select(InterviewSession).order_by(desc(InterviewSession.id)).limit(limit)).all()
        return [{"id":r.id,"job_title":r.job_title,"question":r.question,"answer":r.answer,"evaluation":json.loads(r.evaluation) if r.evaluation else None,"created_at":r.created_at.isoformat()} for r in rows]


def get_latest_plan(job_id):
    with SessionLocal() as db:
        row=db.scalar(select(LearningPlanRecord).where(LearningPlanRecord.job_id==job_id).order_by(desc(LearningPlanRecord.id)))
        return {"id":row.id,"plan":json.loads(row.payload)} if row else None

def update_plan_progress(plan_id, completed):
    with SessionLocal() as db:
        row=db.get(LearningPlanRecord,plan_id)
        if row is None: return False
        plan=json.loads(row.payload)
        for index,item in enumerate(plan): item["completed"] = index in completed
        row.payload=json.dumps(plan);db.commit();return True
