# backend/main.py
# =============================================================================
# Hakutaku AI Challenge — API FastAPI
# Endpoints:
#   POST /extract          → processa um documento (texto livre)
#   GET  /graph            → retorna todas as entidades para o React Flow
#   GET  /proposals        → retorna proposals determinísticos
#   GET  /context          → retorna o AccumulatedContext mais recente
#   GET  /health           → healthcheck
# =============================================================================

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.database import engine, init_db, load_latest_context
from backend.extractor import run_extraction
from backend.proposals import generate_proposals
from backend.models import (
    Decision,
    OpenQuestion,
    Person,
    PersonProjectLink,
    Project,
    Risk,
    Task,
    TaskPersonLink,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# =============================================================================
# Lifespan — inicializa o banco na subida da aplicação
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Hakutaku API iniciada.")
    yield
    logger.info("Hakutaku API encerrada.")


# =============================================================================
# App
# =============================================================================

app = FastAPI(
    title="Hakutaku API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # em produção, restringir para o domínio do frontend
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Schemas de entrada/saída
# =============================================================================

class ExtractRequest(BaseModel):
    document_text: str
    source_doc: str


class ExtractResponse(BaseModel):
    source_doc: str
    parse_errors: int
    counts: dict   # {"projects": int, "persons": int, ...}


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /extract
# ---------------------------------------------------------------------------

@app.post("/extract", response_model=ExtractResponse)
def extract(body: ExtractRequest):
    """
    Recebe um documento em texto livre, roda o pipeline de 3 etapas
    (extrator LLM → relações LLM → persistência) e retorna um resumo.
    """
    if not body.document_text.strip():
        raise HTTPException(status_code=422, detail="document_text não pode ser vazio.")
    if not body.source_doc.strip():
        raise HTTPException(status_code=422, detail="source_doc não pode ser vazio.")

    try:
        result = run_extraction(
            document_text=body.document_text,
            source_doc=body.source_doc,
        )
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.exception("Erro inesperado no pipeline de extração")
        raise HTTPException(status_code=500, detail=f"Erro interno: {e}")

    extraction = result["extraction"]
    counts = {
        "projects":       len(extraction.get("projects", [])),
        "persons":        len(extraction.get("persons", [])),
        "tasks":          len(extraction.get("tasks", [])),
        "risks":          len(extraction.get("risks", [])),
        "decisions":      len(extraction.get("decisions", [])),
        "open_questions": len(extraction.get("open_questions", [])),
        "relations":      len(result.get("relations", [])),
    }

    return ExtractResponse(
        source_doc=result["source_doc"],
        parse_errors=result["parse_errors"],
        counts=counts,
    )


# ---------------------------------------------------------------------------
# GET /graph
# ---------------------------------------------------------------------------

@app.get("/graph")
def graph():
    """
    Retorna todas as entidades e relações formatadas para o React Flow.

    Estrutura de retorno:
    {
        "nodes": [ { "id": str, "type": str, "data": {...} } ],
        "edges": [ { "id": str, "source": str, "target": str, "label": str } ]
    }
    """
    with Session(engine) as session:
        projects       = session.exec(select(Project)).all()
        persons        = session.exec(select(Person)).all()
        tasks          = session.exec(select(Task)).all()
        risks          = session.exec(select(Risk)).all()
        decisions      = session.exec(select(Decision)).all()
        open_questions = session.exec(select(OpenQuestion)).all()
        task_links     = session.exec(select(TaskPersonLink)).all()
        person_links   = session.exec(select(PersonProjectLink)).all()

    nodes = []
    edges = []

    # ── Nodes ────────────────────────────────────────────────────────────────

    for p in projects:
        nodes.append({
            "id": f"project-{p.id}",
            "type": "project",
            "data": {
                "id": p.id,
                "label": p.name,
                "status": p.status,
                "description": p.description,
            },
        })

    for p in persons:
        nodes.append({
            "id": f"person-{p.id}",
            "type": "person",
            "data": {
                "id": p.id,
                "label": p.name,
                "role": p.role,
                "status": p.status,
            },
        })

    for t in tasks:
        nodes.append({
            "id": f"task-{t.id}",
            "type": "task",
            "data": {
                "id": t.id,
                "label": t.title,
                "status": t.status,
                "priority": t.priority,
                "deadline": t.deadline,
            },
        })

    for r in risks:
        nodes.append({
            "id": f"risk-{r.id}",
            "type": "risk",
            "data": {
                "id": r.id,
                "label": r.title,
                "status": r.status,
                "severity": r.severity,
            },
        })

    for d in decisions:
        nodes.append({
            "id": f"decision-{d.id}",
            "type": "decision",
            "data": {
                "id": d.id,
                "label": d.title,
                "status": d.status,
                "decided_by": d.decided_by,
            },
        })

    for q in open_questions:
        nodes.append({
            "id": f"question-{q.id}",
            "type": "openquestion",
            "data": {
                "id": q.id,
                "label": q.title,
                "status": q.status,
                "asked_by": q.asked_by,
            },
        })

    # ── Edges ────────────────────────────────────────────────────────────────

    # Task → Project (belongs_to)
    for t in tasks:
        if t.project_id:
            edges.append({
                "id": f"task-{t.id}-belongs_to-project-{t.project_id}",
                "source": f"task-{t.id}",
                "target": f"project-{t.project_id}",
                "label": "belongs_to",
            })

    # Risk → Project (threatens)
    for r in risks:
        if r.project_id:
            edges.append({
                "id": f"risk-{r.id}-threatens-project-{r.project_id}",
                "source": f"risk-{r.id}",
                "target": f"project-{r.project_id}",
                "label": "threatens",
            })

    # Decision → OpenQuestion (answers)
    for d in decisions:
        if d.answers_question_id:
            edges.append({
                "id": f"decision-{d.id}-answers-question-{d.answers_question_id}",
                "source": f"decision-{d.id}",
                "target": f"question-{d.answers_question_id}",
                "label": "answers",
            })

    # Task → Person (assigned_to)
    for link in task_links:
        edges.append({
            "id": f"task-{link.task_id}-assigned_to-person-{link.person_id}",
            "source": f"task-{link.task_id}",
            "target": f"person-{link.person_id}",
            "label": "assigned_to",
        })

    # Person → Project (member_of)
    for link in person_links:
        edges.append({
            "id": f"person-{link.person_id}-member_of-project-{link.project_id}",
            "source": f"person-{link.person_id}",
            "target": f"project-{link.project_id}",
            "label": "member_of",
        })

    return {"nodes": nodes, "edges": edges}


# ---------------------------------------------------------------------------
# GET /proposals
# ---------------------------------------------------------------------------

@app.get("/proposals")
def proposals():
    """
    Roda as regras determinísticas e retorna a lista de proposals.
    Read-only — não persiste nada.
    """
    try:
        result = generate_proposals()
    except Exception as e:
        logger.exception("Erro ao gerar proposals")
        raise HTTPException(status_code=500, detail=f"Erro interno: {e}")

    return {"proposals": result, "count": len(result)}


# ---------------------------------------------------------------------------
# GET /context
# ---------------------------------------------------------------------------

@app.get("/context")
def context():
    """
    Retorna o AccumulatedContext mais recente (snapshot JSON do estado atual).
    Útil para debug e para o frontend exibir métricas gerais.
    """
    ctx = load_latest_context()
    if ctx is None:
        return {"context": None, "message": "Nenhum documento processado ainda."}
    return {"context": ctx}
