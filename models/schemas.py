from __future__ import annotations
import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from bson import ObjectId
from pydantic import BaseModel, Field

class PyObjectId(str):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    @classmethod
    def validate(cls, v: Any) -> str:
        if not ObjectId.is_valid(v):
            raise ValueError(f"'{v}' is not a valid MongoDB ObjectId")
        return str(v)

class JobStatus(str, Enum):
    DRAFT    = "draft"
    ACTIVE   = "active"
    CLOSED   = "closed"
    ARCHIVED = "archived"

class CandidateStatus(str, Enum):
    RECEIVED       = "received"
    PROCESSING     = "processing"
    SCORED         = "scored"
    SHORTLISTED    = "shortlisted"
    NOT_SELECTED   = "not_selected"
    INTERVIEWING   = "interviewing"
    INTERVIEW_DONE = "interview_done"
    ERROR          = "error"

class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT    = "sent"
    FAILED  = "failed"
    SKIPPED = "skipped"

class MongoBaseModel(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class ScoringWeights(BaseModel):
    education:     float = Field(0.20, ge=0.0, le=1.0)
    experience:    float = Field(0.25, ge=0.0, le=1.0)
    skills:        float = Field(0.20, ge=0.0, le=1.0)
    stability:     float = Field(0.10, ge=0.0, le=1.0)
    progression:   float = Field(0.10, ge=0.0, le=1.0)
    values:        float = Field(0.10, ge=0.0, le=1.0)
    communication: float = Field(0.05, ge=0.0, le=1.0)
    def total(self) -> float:
        return round(self.education + self.experience + self.skills +
                     self.stability + self.progression + self.values +
                     self.communication, 10)

class JobDocument(MongoBaseModel):
    title:                    str            = Field(..., min_length=2, max_length=200)
    department:               Optional[str]  = Field(None)
    description:              str            = Field(..., min_length=50)
    required_skills:          List[str]      = Field(default_factory=list)
    required_education:       str            = Field("")
    required_experience_years:int            = Field(0, ge=0)
    google_form_url:          Optional[str]  = Field(None)
    google_drive_folder_id:   Optional[str]  = Field(None)
    status:                   JobStatus      = Field(JobStatus.DRAFT)
    shortlist_threshold:      int            = Field(65, ge=0, le=100)
    scoring_weights:          ScoringWeights = Field(default_factory=ScoringWeights)
    values_prompt:            str            = Field("")
    total_applications:       int            = Field(0, ge=0)
    shortlisted_count:        int            = Field(0, ge=0)

class WorkExperienceEntry(BaseModel):
    job_title:       str           = Field("")
    company:         str           = Field("")
    start_date:      Optional[str] = Field(None)
    end_date:        Optional[str] = Field(None)
    duration_months: Optional[int] = Field(None)
    description:     str           = Field("")
    is_current:      bool          = Field(False)

class EducationEntry(BaseModel):
    degree:          str           = Field("")
    field_of_study:  str           = Field("")
    institution:     str           = Field("")
    graduation_year: Optional[int] = Field(None)

class CandidateDocument(MongoBaseModel):
    job_id:                  str                    = Field(...)
    full_name:               str                    = Field("")
    email:                   str                    = Field("")
    phone:                   Optional[str]          = Field(None)
    status:                  CandidateStatus        = Field(CandidateStatus.RECEIVED)
    google_drive_file_id:    Optional[str]          = Field(None)
    google_form_response_id: Optional[str]          = Field(None)
    cv_file_path:            Optional[str]          = Field(None)
    cv_file_name:            Optional[str]          = Field(None)
    raw_cv_text:             Optional[str]          = Field(None)
    work_experience:         List[WorkExperienceEntry] = Field(default_factory=list)
    education:               List[EducationEntry]   = Field(default_factory=list)
    skills_extracted:        List[str]              = Field(default_factory=list)
    final_score:             Optional[float]        = Field(None)
    error_message:           Optional[str]          = Field(None)

class ParameterScore(BaseModel):
    score:                float = Field(..., ge=0.0, le=10.0)
    justification:        str   = Field("")
    weighted_contribution:float = Field(0.0)

class ScoreDocument(MongoBaseModel):
    candidate_id:             str                    = Field(...)
    job_id:                   str                    = Field(...)
    education:                Optional[ParameterScore] = Field(None)
    experience:               Optional[ParameterScore] = Field(None)
    skills:                   Optional[ParameterScore] = Field(None)
    stability:                Optional[ParameterScore] = Field(None)
    progression:              Optional[ParameterScore] = Field(None)
    values:                   Optional[ParameterScore] = Field(None)
    communication:            Optional[ParameterScore] = Field(None)
    final_score:              float                  = Field(0.0)
    is_shortlisted:           bool                   = Field(False)
    weights_used:             Dict[str, float]       = Field(default_factory=dict)
    llm_model_used:           str                    = Field("")
    scoring_duration_seconds: Optional[float]        = Field(None)

class InterviewQuestion(BaseModel):
    question_number:  int            = Field(..., ge=1)
    question_text:    str            = Field(...)
    ideal_answer:     Optional[str]  = Field(None)
    answer_text:      Optional[str]  = Field(None)
    similarity_score: Optional[float]= Field(None, ge=0.0, le=1.0)
    llm_feedback:     Optional[str]  = Field(None)

class InterviewDocument(MongoBaseModel):
    candidate_id:               str                    = Field(...)
    job_id:                     str                    = Field(...)
    status:                     str                    = Field("pending")
    questions:                  List[InterviewQuestion]= Field(default_factory=list)
    overall_interview_score:    Optional[float]        = Field(None)
    interview_duration_minutes: Optional[float]        = Field(None)
    completed_at:               Optional[datetime.datetime] = Field(None)

class NotificationDocument(MongoBaseModel):
    candidate_id:      str                 = Field(...)
    job_id:            str                 = Field(...)
    recipient_email:   str                 = Field(...)
    recipient_name:    str                 = Field("")
    subject:           str                 = Field("")
    body_text:         str                 = Field("")
    notification_type: str                 = Field("shortlist")
    status:            NotificationStatus  = Field(NotificationStatus.PENDING)
    error_message:     Optional[str]       = Field(None)
    sent_at:           Optional[datetime.datetime] = Field(None)

class SystemConfigDocument(MongoBaseModel):
    key:            str  = Field(..., min_length=1)
    value:          Any  = Field(...)
    description:    str  = Field("")
    editable_in_ui: bool = Field(True)
