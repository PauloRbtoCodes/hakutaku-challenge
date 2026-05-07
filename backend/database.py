"""
database.py — Hakutaku AI Challenge
Responsabilidades:
  1. Criar tabelas no SQLite na inicialização
  2. INSERT — entidade nova → insere
  3. UPDATE_STATE — entidade existente com estado diferente → atualiza
  4. ENRICH — entidade existente com campos nulos → enriquece
  5. Resolver FKs — lê metadados temporários e faz SELECT para setar IDs corretos
  6. Atualizar AccumulatedContext — snapshot JSON após cada documento processado
"""

import json
import logging
from datetime import datetime
from typing import Optional

from sqlmodel import Session, SQLModel, create_engine, select

from backend.models import (
    AccumulatedContext,
    Decision,
    OpenQuestion,
    OpenQuestionStatus,
    Person,
    PersonProjectLink,
    PersonStatus,
    Project,
    Risk,
    RiskStatus,
    Task,
    TaskPersonLink,
    TaskStatus,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

DATABASE_URL = "sqlite:///./hakutaku.db"
engine = create_engine(DATABASE_URL, echo=False)


def init_db() -> None:
    """Cria todas as tabelas se ainda não existirem."""
    SQLModel.metadata.create_all(engine)
    logger.info("Database initialized.")


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _now() -> datetime:
    # Consistente com models.py que usa datetime.utcnow (sem timezone)
    return datetime.utcnow()


def _merge_aliases(existing: Optional[str], incoming: list[str]) -> Optional[str]:
    """Une aliases existentes (JSON string) com novas, sem duplicatas."""
    if not incoming:
        return existing
    current: list[str] = json.loads(existing) if existing else []
    merged = list(dict.fromkeys(current + incoming))
    return json.dumps(merged, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Upserts — INSERT / UPDATE_STATE / ENRICH
# ---------------------------------------------------------------------------

def _upsert_project(session: Session, p: Project) -> Project:
    existing = session.exec(select(Project).where(Project.name == p.name)).first()

    if existing is None:
        session.add(p)
        session.flush()
        logger.info("INSERT Project '%s'", p.name)
        return p

    changed = False
    # UPDATE_STATE
    if p.status is not None and p.status != existing.status:
        logger.info("UPDATE_STATE Project '%s': %s → %s", existing.name, existing.status, p.status)
        existing.status = p.status
        changed = True
    # ENRICH — Project só tem description além de name/status
    if p.description and not existing.description:
        existing.description = p.description
        changed = True

    if changed:
        existing.updated_at = _now()
        session.add(existing)
        session.flush()
    return existing


def _upsert_person(session: Session, p: Person) -> Person:
    existing = session.exec(select(Person).where(Person.name == p.name)).first()

    if existing is None:
        session.add(p)
        session.flush()
        logger.info("INSERT Person '%s'", p.name)
        return p

    changed = False
    if p.status is not None and p.status != existing.status:
        logger.info("UPDATE_STATE Person '%s': %s → %s", existing.name, existing.status, p.status)
        existing.status = p.status
        changed = True
    # ENRICH — role e aliases (Person não tem email no model)
    if p.role and not existing.role:
        existing.role = p.role
        changed = True
    if p.aliases:
        incoming = json.loads(p.aliases)
        merged = _merge_aliases(existing.aliases, incoming)
        if merged != existing.aliases:
            existing.aliases = merged
            changed = True

    if changed:
        existing.updated_at = _now()
        session.add(existing)
        session.flush()
    return existing


def _upsert_task(session: Session, t: Task) -> Task:
    existing = session.exec(select(Task).where(Task.title == t.title)).first()

    if existing is None:
        session.add(t)
        session.flush()
        logger.info("INSERT Task '%s'", t.title)
        return t

    changed = False
    if t.status is not None and t.status != existing.status:
        logger.info("UPDATE_STATE Task '%s': %s → %s", existing.title, existing.status, t.status)
        existing.status = t.status
        changed = True
    if t.deadline and not existing.deadline:
        existing.deadline = t.deadline
        changed = True
    if t.priority and not existing.priority:
        existing.priority = t.priority
        changed = True
    if t.description and not existing.description:
        existing.description = t.description
        changed = True
    if t.project_id and not existing.project_id:
        existing.project_id = t.project_id
        changed = True

    if changed:
        existing.updated_at = _now()
        session.add(existing)
        session.flush()
    return existing


def _upsert_risk(session: Session, r: Risk) -> Risk:
    existing = session.exec(select(Risk).where(Risk.title == r.title)).first()

    if existing is None:
        session.add(r)
        session.flush()
        logger.info("INSERT Risk '%s'", r.title)
        return r

    changed = False
    # UPDATE_STATE — severidade só sobe, exceto mitigated/dismissed explícito
    severity_order = {
        RiskStatus.open: 1, RiskStatus.critical: 2,
        RiskStatus.mitigated: 0, RiskStatus.dismissed: 0,
    }
    if r.status is not None:
        new_ord = severity_order.get(r.status, 0)
        cur_ord = severity_order.get(existing.status, 0)
        if new_ord > cur_ord:
            logger.info("UPDATE_STATE Risk '%s': %s → %s", existing.title, existing.status, r.status)
            existing.status = r.status
            changed = True
        elif r.status in (RiskStatus.mitigated, RiskStatus.dismissed) and new_ord < cur_ord:
            logger.info("UPDATE_STATE Risk '%s': %s → %s (resolvido)", existing.title, existing.status, r.status)
            existing.status = r.status
            changed = True
    # ENRICH — severity numérica só sobe
    if r.severity is not None and r.severity > (existing.severity or 0):
        existing.severity = r.severity
        changed = True
    if r.description and not existing.description:
        existing.description = r.description
        changed = True
    if r.project_id and not existing.project_id:
        existing.project_id = r.project_id
        changed = True

    if changed:
        existing.updated_at = _now()
        session.add(existing)
        session.flush()
    return existing


def _upsert_decision(session: Session, d: Decision) -> Decision:
    existing = session.exec(select(Decision).where(Decision.title == d.title)).first()

    if existing is None:
        session.add(d)
        session.flush()
        logger.info("INSERT Decision '%s'", d.title)
        return d

    changed = False
    if d.status is not None and d.status != existing.status:
        logger.info("UPDATE_STATE Decision '%s': %s → %s", existing.title, existing.status, d.status)
        existing.status = d.status
        changed = True
    # ENRICH — campo é decided_by (não made_by)
    if d.decided_by and not existing.decided_by:
        existing.decided_by = d.decided_by
        changed = True
    if d.description and not existing.description:
        existing.description = d.description
        changed = True
    if d.answers_question_id and not existing.answers_question_id:
        existing.answers_question_id = d.answers_question_id
        changed = True

    if changed:
        existing.updated_at = _now()
        session.add(existing)
        session.flush()
    return existing


def _upsert_open_question(session: Session, q: OpenQuestion) -> OpenQuestion:
    existing = session.exec(select(OpenQuestion).where(OpenQuestion.title == q.title)).first()

    if existing is None:
        session.add(q)
        session.flush()
        logger.info("INSERT OpenQuestion '%s'", q.title)
        return q

    changed = False
    if q.status is not None and q.status != existing.status:
        logger.info("UPDATE_STATE OpenQuestion '%s': %s → %s", existing.title, existing.status, q.status)
        existing.status = q.status
        changed = True
    if q.description and not existing.description:
        existing.description = q.description
        changed = True

    if changed:
        existing.updated_at = _now()
        session.add(existing)
        session.flush()
    return existing


# ---------------------------------------------------------------------------
# Resolver FKs
# ---------------------------------------------------------------------------

def _resolve_task_fks(session: Session, task: Task, raw: Task) -> None:
    """Resolve project_id e TaskPersonLink a partir dos metadados temporários do parser."""
    project_name: Optional[str] = raw.__dict__.get("_project_name")
    if project_name and not task.project_id:
        proj = session.exec(select(Project).where(Project.name == project_name)).first()
        if proj:
            task.project_id = proj.id
            session.add(task)
            session.flush()
        else:
            logger.warning("Task '%s': project '%s' não encontrado", task.title, project_name)

    assignee_names: list[str] = raw.__dict__.get("_assignee_names") or []
    if not assignee_names:
        existing_links = session.exec(
            select(TaskPersonLink).where(TaskPersonLink.task_id == task.id)
        ).all()
        if not existing_links and task.status not in (TaskStatus.done, TaskStatus.orphan):
            task.status = TaskStatus.orphan
            session.add(task)
            session.flush()
            logger.info("Task '%s' marcada orphan", task.title)
    else:
        for name in assignee_names:
            person = session.exec(select(Person).where(Person.name == name)).first()
            if not person:
                person = Person(name=name, status=PersonStatus.active)
                session.add(person)
                session.flush()
                logger.info("INSERT Person implícita '%s'", name)
            link = session.exec(
                select(TaskPersonLink).where(
                    TaskPersonLink.task_id == task.id,
                    TaskPersonLink.person_id == person.id,
                )
            ).first()
            if not link:
                session.add(TaskPersonLink(task_id=task.id, person_id=person.id))
                session.flush()
        # Remove orphan se agora tem assignee
        if task.status == TaskStatus.orphan:
            task.status = TaskStatus.open
            session.add(task)
            session.flush()


def _resolve_risk_fks(session: Session, risk: Risk, raw: Risk) -> None:
    project_name: Optional[str] = raw.__dict__.get("_project_name")
    if project_name and not risk.project_id:
        proj = session.exec(select(Project).where(Project.name == project_name)).first()
        if proj:
            risk.project_id = proj.id
            session.add(risk)
            session.flush()
        else:
            logger.warning("Risk '%s': project '%s' não encontrado", risk.title, project_name)


def _resolve_decision_fks(session: Session, decision: Decision, raw: Decision) -> None:
    """Momento 'uau': Decision responde OpenQuestion → muda status da pergunta."""
    q_title: Optional[str] = raw.__dict__.get("_answers_question_title")
    if q_title and not decision.answers_question_id:
        q = session.exec(select(OpenQuestion).where(OpenQuestion.title == q_title)).first()
        if q:
            decision.answers_question_id = q.id
            if q.status == OpenQuestionStatus.open:
                q.status = OpenQuestionStatus.answered
                q.updated_at = _now()
                session.add(q)
            session.add(decision)
            session.flush()
            logger.info("Decision '%s' responde OpenQuestion '%s' ✓", decision.title, q.title)
        else:
            logger.warning("Decision '%s': OpenQuestion '%s' não encontrada", decision.title, q_title)


def _resolve_person_project_links(session: Session, person: Person, project_names: list[str]) -> None:
    for name in project_names:
        proj = session.exec(select(Project).where(Project.name == name)).first()
        if not proj:
            continue
        link = session.exec(
            select(PersonProjectLink).where(
                PersonProjectLink.person_id == person.id,
                PersonProjectLink.project_id == proj.id,
            )
        ).first()
        if not link:
            session.add(PersonProjectLink(person_id=person.id, project_id=proj.id))
            session.flush()


# ---------------------------------------------------------------------------
# Aplicar relações do Prompt 2
# parsers.py retorna: from_type, from_title, relation, to_type, to_title
# ---------------------------------------------------------------------------

def _apply_relations(session: Session, relations: list[dict]) -> None:
    for rel in relations:
        from_type  = rel.get("from_type")
        from_title = rel.get("from_title")
        relation   = rel.get("relation")
        to_type    = rel.get("to_type")
        to_title   = rel.get("to_title")

        if not all([from_type, from_title, relation, to_type, to_title]):
            continue

        try:
            if relation == "belongs_to" and from_type == "Task" and to_type == "Project":
                task = session.exec(select(Task).where(Task.title == from_title)).first()
                proj = session.exec(select(Project).where(Project.name == to_title)).first()
                if task and proj and not task.project_id:
                    task.project_id = proj.id
                    session.add(task)

            elif relation == "assigned_to" and from_type == "Task" and to_type == "Person":
                task = session.exec(select(Task).where(Task.title == from_title)).first()
                person = session.exec(select(Person).where(Person.name == to_title)).first()
                if task and person:
                    link = session.exec(
                        select(TaskPersonLink).where(
                            TaskPersonLink.task_id == task.id,
                            TaskPersonLink.person_id == person.id,
                        )
                    ).first()
                    if not link:
                        session.add(TaskPersonLink(task_id=task.id, person_id=person.id))
                    if task.status == TaskStatus.orphan:
                        task.status = TaskStatus.open
                        session.add(task)

            elif relation == "threatens" and from_type == "Risk" and to_type == "Project":
                risk = session.exec(select(Risk).where(Risk.title == from_title)).first()
                proj = session.exec(select(Project).where(Project.name == to_title)).first()
                if risk and proj and not risk.project_id:
                    risk.project_id = proj.id
                    session.add(risk)

            elif relation == "answers" and from_type == "Decision" and to_type == "OpenQuestion":
                decision = session.exec(select(Decision).where(Decision.title == from_title)).first()
                q = session.exec(select(OpenQuestion).where(OpenQuestion.title == to_title)).first()
                if decision and q:
                    if not decision.answers_question_id:
                        decision.answers_question_id = q.id
                        session.add(decision)
                    if q.status == OpenQuestionStatus.open:
                        q.status = OpenQuestionStatus.answered
                        q.updated_at = _now()
                        session.add(q)
                    logger.info("answers: '%s' → '%s' ✓", from_title, to_title)

            elif relation == "member_of" and from_type == "Person" and to_type == "Project":
                person = session.exec(select(Person).where(Person.name == from_title)).first()
                proj = session.exec(select(Project).where(Project.name == to_title)).first()
                if person and proj:
                    _resolve_person_project_links(session, person, [proj.name])

        except Exception as exc:
            logger.warning("Falha ao aplicar relação %s: %s", rel, exc)


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def persist_extraction(extraction: dict, relations: list[dict], source_doc: str) -> None:
    """
    Persiste um documento completo no banco.

    Args:
        extraction: dict de parse_extraction_result() — chaves: projects, persons,
                    tasks, risks, decisions, open_questions (cada valor é lista de SQLModel)
        relations:  list[dict] de parse_relations_result()
        source_doc: identificador do documento (ex: "reuniao_1.txt")

    Ordem: Project → Person → OpenQuestion → Task → Risk → Decision
    (garante que FKs existam antes de serem referenciadas)
    """
    with Session(engine) as session:

        for raw in extraction.get("projects", []):
            _upsert_project(session, raw)

        for raw in extraction.get("persons", []):
            person = _upsert_person(session, raw)
            proj_names: list[str] = raw.__dict__.get("_project_names") or []
            if proj_names:
                _resolve_person_project_links(session, person, proj_names)

        # OpenQuestion ANTES de Decision para FK funcionar
        for raw in extraction.get("open_questions", []):
            _upsert_open_question(session, raw)

        for raw in extraction.get("tasks", []):
            task = _upsert_task(session, raw)
            _resolve_task_fks(session, task, raw)

        for raw in extraction.get("risks", []):
            risk = _upsert_risk(session, raw)
            _resolve_risk_fks(session, risk, raw)

        for raw in extraction.get("decisions", []):
            decision = _upsert_decision(session, raw)
            _resolve_decision_fks(session, decision, raw)

        _apply_relations(session, relations)
        session.commit()
        logger.info("Documento '%s' persistido.", source_doc)

    _update_accumulated_context(source_doc)


# ---------------------------------------------------------------------------
# AccumulatedContext
# ---------------------------------------------------------------------------

def _update_accumulated_context(source_doc: str) -> None:
    """
    Salva snapshot do estado atual. Campos alinhados com models.py:
    snapshot_json, last_source_doc, document_count.
    """
    with Session(engine) as session:
        projects       = session.exec(select(Project)).all()
        persons        = session.exec(select(Person)).all()
        tasks          = session.exec(select(Task)).all()
        risks          = session.exec(select(Risk)).all()
        decisions      = session.exec(select(Decision)).all()
        open_questions = session.exec(select(OpenQuestion)).all()
        doc_count      = len(session.exec(select(AccumulatedContext)).all()) + 1

        snapshot = {
            "generated_at":    _now().isoformat(),
            "last_source_doc": source_doc,
            "document_count":  doc_count,
            "projects": [
                {"id": p.id, "name": p.name, "status": p.status.value if p.status else None}
                for p in projects
            ],
            "persons": [
                {
                    "id": p.id, "name": p.name, "role": p.role,
                    "status": p.status.value if p.status else None,
                    "aliases": json.loads(p.aliases) if p.aliases else [],
                }
                for p in persons
            ],
            "tasks": [
                {
                    "id": t.id, "title": t.title,
                    "status": t.status.value if t.status else None,
                    "deadline": t.deadline, "project_id": t.project_id,
                    "priority": t.priority,
                }
                for t in tasks
            ],
            "risks": [
                {
                    "id": r.id, "title": r.title,
                    "status": r.status.value if r.status else None,
                    "severity": r.severity, "project_id": r.project_id,
                }
                for r in risks
            ],
            "decisions": [
                {
                    "id": d.id, "title": d.title,
                    "status": d.status.value if d.status else None,
                    "answers_question_id": d.answers_question_id,
                }
                for d in decisions
            ],
            "open_questions": [
                {
                    "id": q.id, "title": q.title,
                    "status": q.status.value if q.status else None,
                }
                for q in open_questions
            ],
        }

        ctx = AccumulatedContext(
            snapshot_json=json.dumps(snapshot, ensure_ascii=False, indent=2),
            document_count=doc_count,
            last_source_doc=source_doc,
            updated_at=_now(),
        )
        session.add(ctx)
        session.commit()
        logger.info("AccumulatedContext doc #%d salvo.", doc_count)


def load_latest_context() -> Optional[dict]:
    """Retorna o snapshot mais recente, ou None se nenhum doc foi processado."""
    with Session(engine) as session:
        ctx = session.exec(
            select(AccumulatedContext).order_by(AccumulatedContext.updated_at.desc())
        ).first()
        if ctx is None:
            return None
        return json.loads(ctx.snapshot_json)


def build_context_block(context: Optional[dict]) -> str:
    """
    Texto estruturado para injetar nos Prompts 1 e 2.
    Filtra entidades encerradas para manter o prompt enxuto.
    """
    if not context:
        return "<!-- Primeiro documento — nenhum contexto acumulado ainda. -->"

    lines = [
        "## Contexto Organizacional Acumulado",
        f"_Documentos processados: {context.get('document_count', '?')} | "
        f"Último: {context.get('last_source_doc', '?')}_",
        "",
    ]

    if context["projects"]:
        lines.append("### Projetos conhecidos")
        for p in context["projects"]:
            lines.append(f"- [{p['id']}] {p['name']} (status: {p['status']})")
        lines.append("")

    if context["persons"]:
        lines.append("### Pessoas conhecidas")
        for p in context["persons"]:
            aliases = ", ".join(p["aliases"]) if p["aliases"] else "—"
            lines.append(f"- [{p['id']}] {p['name']} | role: {p['role'] or '?'} | aliases: {aliases}")
        lines.append("")

    open_tasks = [t for t in context["tasks"] if t["status"] != "done"]
    if open_tasks:
        lines.append("### Tarefas em aberto")
        for t in open_tasks:
            lines.append(f"- [{t['id']}] {t['title']} | status: {t['status']} | deadline: {t['deadline'] or '?'}")
        lines.append("")

    active_risks = [r for r in context["risks"] if r["status"] not in ("mitigated", "dismissed")]
    if active_risks:
        lines.append("### Riscos ativos")
        for r in active_risks:
            lines.append(f"- [{r['id']}] {r['title']} | status: {r['status']} | severity: {r['severity']}")
        lines.append("")

    open_qs = [q for q in context["open_questions"] if q["status"] == "open"]
    if open_qs:
        lines.append("### Perguntas abertas")
        for q in open_qs:
            lines.append(f"- [{q['id']}] {q['title']}")
        lines.append("")

    if context.get("decisions"):
        lines.append("### Decisões registradas")
        for d in context["decisions"]:
            lines.append(f"- [{d['id']}] {d['title']} (status: {d['status']})")
        lines.append("")

    return "\n".join(lines)
