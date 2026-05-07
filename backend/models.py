# backend/models.py
# =============================================================================
# Ontologia do sistema Hakutaku — 6 entidades, estados, relações
# Compatível com SQLModel 0.0.21 + SQLAlchemy 2.x
# Relações de lista removidas (não usadas em database.py — queries diretas)
# =============================================================================

from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List
from sqlmodel import Field, SQLModel, Relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# =============================================================================
# ENUMS
# =============================================================================

class TaskStatus(str, Enum):
    open        = "open"
    in_progress = "in_progress"
    done        = "done"
    overdue     = "overdue"
    orphan      = "orphan"

class RiskStatus(str, Enum):
    open      = "open"
    critical  = "critical"
    mitigated = "mitigated"
    dismissed = "dismissed"

class DecisionStatus(str, Enum):
    proposed = "proposed"
    approved = "approved"
    reversed = "reversed"

class OpenQuestionStatus(str, Enum):
    open     = "open"
    answered = "answered"
    dropped  = "dropped"

class PersonStatus(str, Enum):
    active   = "active"
    inactive = "inactive"

class ProjectStatus(str, Enum):
    active = "active"
    paused = "paused"
    done   = "done"


# =============================================================================
# TABELAS DE ASSOCIAÇÃO (many-to-many)
# =============================================================================

class PersonProjectLink(SQLModel, table=True):
    """Person → Project (member_of). Detecta SPOF."""
    __tablename__ = "person_project_link"
    person_id  : Optional[int] = Field(default=None, foreign_key="person.id", primary_key=True)
    project_id : Optional[int] = Field(default=None, foreign_key="project.id", primary_key=True)


class TaskPersonLink(SQLModel, table=True):
    """Task → Person (assigned_to). Detecta orphan."""
    __tablename__ = "task_person_link"
    task_id   : Optional[int] = Field(default=None, foreign_key="task.id", primary_key=True)
    person_id : Optional[int] = Field(default=None, foreign_key="person.id", primary_key=True)


# =============================================================================
# ENTIDADES
# =============================================================================

class Project(SQLModel, table=True):
    __tablename__ = "project"
    id          : Optional[int] = Field(default=None, primary_key=True)
    name        : str           = Field(index=True)
    status      : ProjectStatus = Field(default=ProjectStatus.active)
    description : Optional[str] = Field(default=None)
    source_doc  : Optional[str] = Field(default=None)
    created_at  : datetime      = Field(default_factory=_utcnow)
    updated_at  : datetime      = Field(default_factory=_utcnow)


class Person(SQLModel, table=True):
    __tablename__ = "person"
    id         : Optional[int] = Field(default=None, primary_key=True)
    name       : str           = Field(index=True)
    aliases    : Optional[str] = Field(default=None)   # JSON list
    role       : Optional[str] = Field(default=None)
    status     : PersonStatus  = Field(default=PersonStatus.active)
    source_doc : Optional[str] = Field(default=None)
    created_at : datetime      = Field(default_factory=_utcnow)
    updated_at : datetime      = Field(default_factory=_utcnow)


class Task(SQLModel, table=True):
    __tablename__ = "task"
    id          : Optional[int] = Field(default=None, primary_key=True)
    title       : str
    description : Optional[str] = Field(default=None)
    status      : TaskStatus    = Field(default=TaskStatus.open)
    deadline    : Optional[str] = Field(default=None)   # ISO 8601
    priority    : Optional[str] = Field(default=None)   # low|normal|high|critical
    project_id  : Optional[int] = Field(default=None, foreign_key="project.id")
    source_doc  : Optional[str] = Field(default=None)
    created_at  : datetime      = Field(default_factory=_utcnow)
    updated_at  : datetime      = Field(default_factory=_utcnow)


class Risk(SQLModel, table=True):
    __tablename__ = "risk"
    id          : Optional[int] = Field(default=None, primary_key=True)
    title       : str
    description : Optional[str] = Field(default=None)
    status      : RiskStatus    = Field(default=RiskStatus.open)
    severity    : int           = Field(default=5)      # 1–10
    project_id  : Optional[int] = Field(default=None, foreign_key="project.id")
    source_doc  : Optional[str] = Field(default=None)
    created_at  : datetime      = Field(default_factory=_utcnow)
    updated_at  : datetime      = Field(default_factory=_utcnow)


class OpenQuestion(SQLModel, table=True):
    __tablename__ = "openquestion"
    id          : Optional[int]      = Field(default=None, primary_key=True)
    title       : str
    description : Optional[str]      = Field(default=None)
    status      : OpenQuestionStatus = Field(default=OpenQuestionStatus.open)
    asked_by    : Optional[str]      = Field(default=None)
    source_doc  : Optional[str]      = Field(default=None)
    created_at  : datetime           = Field(default_factory=_utcnow)
    updated_at  : datetime           = Field(default_factory=_utcnow)


class Decision(SQLModel, table=True):
    __tablename__ = "decision"
    id                  : Optional[int]  = Field(default=None, primary_key=True)
    title               : str
    description         : Optional[str]  = Field(default=None)
    status              : DecisionStatus = Field(default=DecisionStatus.approved)
    decided_by          : Optional[str]  = Field(default=None)
    answers_question_id : Optional[int]  = Field(default=None, foreign_key="openquestion.id")
    source_doc          : Optional[str]  = Field(default=None)
    created_at          : datetime       = Field(default_factory=_utcnow)
    updated_at          : datetime       = Field(default_factory=_utcnow)


class AccumulatedContext(SQLModel, table=True):
    """Snapshot JSON do estado atual, injetado nos Prompts 1 e 2."""
    __tablename__ = "accumulated_context"
    id              : Optional[int] = Field(default=None, primary_key=True)
    snapshot_json   : str
    document_count  : int           = Field(default=0)
    last_source_doc : Optional[str] = Field(default=None)
    updated_at      : datetime      = Field(default_factory=_utcnow)
