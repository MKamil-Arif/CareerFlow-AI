"""Request bodies. Every field is bounded so a public API can't be fed huge payloads."""
from __future__ import annotations

from typing import Annotated, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=80)]
LineText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=400)]


class Profile(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    name: str = Field(default="", max_length=120)
    skills: List[ShortText] = Field(default_factory=list, max_length=100)
    experience: List[LineText] = Field(default_factory=list, max_length=50)
    education: List[LineText] = Field(default_factory=list, max_length=30)
    projects: List[LineText] = Field(default_factory=list, max_length=50)
    certifications: List[LineText] = Field(default_factory=list, max_length=50)
    location: str = Field(default="", max_length=160)
    career_level: Literal["Entry", "Mid", "Senior"] = "Entry"

    @field_validator("career_level", mode="before")
    @classmethod
    def _level(cls, value):
        value = str(value or "Entry").strip().title()
        return value if value in {"Entry", "Mid", "Senior"} else "Entry"

    @field_validator("skills", "experience", "education", "projects", "certifications", mode="after")
    @classmethod
    def _drop_empty(cls, values):
        return [v for v in values if v]


class ProfilePayload(BaseModel):
    profile: Profile


class Role(BaseModel):
    """A target role. Either a curated catalog job or one generated for this user.

    Generated roles live only in the user's browser, so the frontend sends the
    whole role back with each request instead of an ID the server would have to store.
    """
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    id: Union[int, Annotated[str, StringConstraints(max_length=64)]]
    title: str = Field(min_length=2, max_length=120)
    field: str = Field(default="", max_length=80)
    company: str = Field(default="", max_length=120)
    location: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=800)
    required_skills: List[ShortText] = Field(default_factory=list, max_length=15)
    preferred_skills: List[ShortText] = Field(default_factory=list, max_length=15)
    education_requirements: str = Field(default="", max_length=300)
    experience_requirements: str = Field(default="", max_length=300)
    source: Literal["catalog", "ai", "custom"] = "catalog"
    why: str = Field(default="", max_length=600)

    @field_validator("required_skills", "preferred_skills", mode="after")
    @classmethod
    def _drop_empty(cls, values):
        return [v for v in values if v]


class JobTargetPayload(ProfilePayload):
    """Target either a curated job by `job_id`, or any role by sending the `job` itself."""
    job_id: Optional[int] = Field(default=None, ge=1)
    job: Optional[Role] = None

    @model_validator(mode="after")
    def _one_target(self):
        if self.job is None and self.job_id is None:
            raise ValueError("send either job_id or job")
        return self


class RecommendPayload(ProfilePayload):
    preference: str = Field(default="", max_length=200)
    exclude: List[Annotated[str, StringConstraints(max_length=120)]] = Field(default_factory=list, max_length=60)
    count: int = Field(default=6, ge=3, le=10)


class CustomRolePayload(ProfilePayload):
    title: str = Field(min_length=2, max_length=120)


class InterviewStartPayload(ProfilePayload):
    job_title: str = Field(min_length=1, max_length=160)
    job_id: Optional[int] = Field(default=None, ge=1)
    job: Optional[Role] = None
    previous: List[Annotated[str, StringConstraints(max_length=1000)]] = Field(default_factory=list, max_length=30)


class InterviewEvalPayload(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    answer: str = Field(min_length=1, max_length=12000)
    job_title: str = Field(min_length=1, max_length=160)
    job_id: Optional[int] = Field(default=None, ge=1)
    job: Optional[Role] = None
