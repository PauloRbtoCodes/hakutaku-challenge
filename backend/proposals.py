# backend/proposals.py
# =============================================================================
# Geração determinística de proposals (zero LLM).
# Read-only: não persiste nada no banco.
# =============================================================================

from sqlmodel import Session, select

from backend.database import engine
from backend.models import (
    Task, TaskPersonLink,
    Risk,
    Decision, OpenQuestion,
    Person, PersonProjectLink,
    Project, AccumulatedContext,
    TaskStatus, RiskStatus, OpenQuestionStatus, ProjectStatus,
)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _get_project_name(session: Session, project_id: int | None) -> str:
    if project_id is None:
        return "projeto desconhecido"
    project = session.get(Project, project_id)
    return project.name if project else f"projeto #{project_id}"


def _get_total_doc_count(session: Session) -> int:
    """Quantos documentos já foram processados no total."""
    ctx = session.exec(select(AccumulatedContext)).first()
    return ctx.document_count if ctx else 0


# ---------------------------------------------------------------------------
# Regras
# ---------------------------------------------------------------------------

def _rule_orphan_tasks(session: Session) -> list[dict]:
    """Task com status orphan → sem responsável."""
    proposals = []
    tasks = session.exec(select(Task).where(Task.status == TaskStatus.orphan)).all()
    for task in tasks:
        project_name = _get_project_name(session, task.project_id)
        proposals.append({
            "type": "orphan_task",
            "title": f"Atribuir responsável para '{task.title}'",
            "description": (
                f"A task '{task.title}' do projeto '{project_name}' "
                "não possui responsável. Defina um assignee para evitar bloqueio."
            ),
            "entity_type": "Task",
            "entity_title": task.title,
            "priority": "medium",
        })
    return proposals


def _rule_overdue_tasks(session: Session) -> list[dict]:
    """Task com status overdue → revisar prazo ou reatribuir."""
    proposals = []
    tasks = session.exec(select(Task).where(Task.status == TaskStatus.overdue)).all()
    for task in tasks:
        # Busca assignees via link table
        links = session.exec(
            select(TaskPersonLink).where(TaskPersonLink.task_id == task.id)
        ).all()
        if links:
            assignee_ids = [lnk.person_id for lnk in links]
            people = [session.get(Person, pid) for pid in assignee_ids]
            assignees_str = ", ".join(p.name for p in people if p)
        else:
            assignees_str = "sem responsável"

        project_name = _get_project_name(session, task.project_id)
        proposals.append({
            "type": "overdue_task",
            "title": f"Task '{task.title}' está atrasada",
            "description": (
                f"A task '{task.title}' do projeto '{project_name}' "
                f"(responsável: {assignees_str}) passou do prazo. "
                "Revisar prazo ou reatribuir."
            ),
            "entity_type": "Task",
            "entity_title": task.title,
            "priority": "high",
        })
    return proposals


def _rule_critical_risks(session: Session) -> list[dict]:
    """Risk severity ≥ 7 e status open ou critical."""
    proposals = []
    risks = session.exec(
        select(Risk).where(
            Risk.status.in_([RiskStatus.open, RiskStatus.critical]),
            Risk.severity >= 7,
        )
    ).all()
    for risk in risks:
        project_name = _get_project_name(session, risk.project_id)
        priority = "critical" if risk.severity >= 9 else "high"
        proposals.append({
            "type": "critical_risk",
            "title": f"Risco crítico '{risk.title}' ameaça '{project_name}'",
            "description": (
                f"O risco '{risk.title}' (severidade {risk.severity}/10, "
                f"status '{risk.status.value}') ameaça o projeto '{project_name}'. "
                "Elaborar plano de mitigação com urgência."
            ),
            "entity_type": "Risk",
            "entity_title": risk.title,
            "priority": priority,
        })
    return proposals


def _rule_answered_questions(session: Session) -> list[dict]:
    """Decision com answers_question_id → OpenQuestion ainda open."""
    proposals = []
    decisions = session.exec(
        select(Decision).where(Decision.answers_question_id.is_not(None))
    ).all()
    for decision in decisions:
        question = session.get(OpenQuestion, decision.answers_question_id)
        if question is None or question.status != OpenQuestionStatus.open:
            continue
        proposals.append({
            "type": "answered_question",
            "title": f"Pergunta '{question.title}' pode ser encerrada",
            "description": (
                f"A decisão '{decision.title}' responde à pergunta '{question.title}', "
                "mas ela ainda está marcada como 'open'. Marcar como encerrada."
            ),
            "entity_type": "OpenQuestion",
            "entity_title": question.title,
            "priority": "low",
        })
    return proposals


def _rule_spof_projects(session: Session) -> list[dict]:
    """Projeto ativo com apenas 1 Person alocada → SPOF."""
    proposals = []
    projects = session.exec(
        select(Project).where(Project.status == ProjectStatus.active)
    ).all()
    for project in projects:
        links = session.exec(
            select(PersonProjectLink).where(PersonProjectLink.project_id == project.id)
        ).all()
        if len(links) != 1:
            continue
        person = session.get(Person, links[0].person_id)
        person_name = person.name if person else "pessoa desconhecida"
        proposals.append({
            "type": "spof",
            "title": f"Projeto '{project.name}' tem ponto único de falha",
            "description": (
                f"O projeto '{project.name}' possui apenas '{person_name}' alocado(a). "
                "Isso representa um SPOF — adicionar mais membros ao projeto."
            ),
            "entity_type": "Project",
            "entity_title": project.name,
            "priority": "high",
        })
    return proposals


def _rule_stale_questions(session: Session) -> list[dict]:
    """OpenQuestion open que apareceu em documento anterior ao mais recente."""
    proposals = []
    total_docs = _get_total_doc_count(session)
    if total_docs <= 1:
        # Com só 1 documento processado, nenhuma pergunta pode ser "antiga"
        return proposals

    # Busca o source_doc mais recente
    latest_ctx = session.exec(select(AccumulatedContext)).first()
    latest_doc = latest_ctx.last_source_doc if latest_ctx else None

    questions = session.exec(
        select(OpenQuestion).where(OpenQuestion.status == OpenQuestionStatus.open)
    ).all()
    for question in questions:
        # Pergunta é "stale" se ela não veio do documento mais recente
        if question.source_doc != latest_doc:
            proposals.append({
                "type": "stale_question",
                "title": f"Pergunta '{question.title}' segue sem resposta",
                "description": (
                    f"A pergunta '{question.title}' está aberta desde '{question.source_doc}' "
                    f"e já foram processados {total_docs} documentos. "
                    "Designar um responsável para resolvê-la."
                ),
                "entity_type": "OpenQuestion",
                "entity_title": question.title,
                "priority": "medium",
            })
    return proposals


# ---------------------------------------------------------------------------
# Ponto de entrada público
# ---------------------------------------------------------------------------

def generate_proposals() -> list[dict]:
    """
    Consulta o banco e aplica as 6 regras determinísticas.
    Read-only — não persiste nada.
    """
    rules = [
        _rule_orphan_tasks,
        _rule_overdue_tasks,
        _rule_critical_risks,
        _rule_answered_questions,
        _rule_spof_projects,
        _rule_stale_questions,
    ]

    all_proposals: list[dict] = []

    with Session(engine) as session:
        for rule in rules:
            try:
                results = rule(session)
                all_proposals.extend(results)
            except Exception as e:
                print(f"[proposals] Regra '{rule.__name__}' falhou: {e}")

    return all_proposals