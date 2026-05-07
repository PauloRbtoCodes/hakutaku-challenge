# backend/test_proposals.py
# =============================================================================
# Testes para proposals.py — banco in-memory, sem tocar no SQLite de produção
# =============================================================================

import pytest
from sqlmodel import Session, SQLModel, create_engine

from backend.models import (
    Task, TaskPersonLink,
    Risk,
    Decision, OpenQuestion,
    Person, PersonProjectLink,
    Project, AccumulatedContext,
    TaskStatus, RiskStatus, DecisionStatus, OpenQuestionStatus,
    ProjectStatus, PersonStatus,
)


# ---------------------------------------------------------------------------
# Fixture: engine in-memory + session isolada por teste
# ---------------------------------------------------------------------------

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Patch: faz generate_proposals usar a session do teste
# ---------------------------------------------------------------------------

def run_rules(session: Session) -> list[dict]:
    """Chama cada regra privada diretamente, sem abrir nova Session."""
    import backend.proposals as p
    results = []
    for rule in [
        p._rule_orphan_tasks,
        p._rule_overdue_tasks,
        p._rule_critical_risks,
        p._rule_answered_questions,
        p._rule_spof_projects,
        p._rule_stale_questions,
    ]:
        results.extend(rule(session))
    return results


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------

def make_project(session, name="Projeto Alpha", status=ProjectStatus.active):
    p = Project(name=name, status=status)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def make_person(session, name="Ana"):
    p = Person(name=name, status=PersonStatus.active)
    session.add(p)
    session.commit()
    session.refresh(p)
    return p


def make_task(session, title="Task X", status=TaskStatus.open, project_id=None):
    t = Task(title=title, status=status, project_id=project_id)
    session.add(t)
    session.commit()
    session.refresh(t)
    return t


def make_risk(session, title="Risco Y", severity=5, status=RiskStatus.open, project_id=None):
    r = Risk(title=title, severity=severity, status=status, project_id=project_id)
    session.add(r)
    session.commit()
    session.refresh(r)
    return r


def make_question(session, title="Pergunta Z", status=OpenQuestionStatus.open, source_doc="doc1.txt"):
    q = OpenQuestion(title=title, status=status, source_doc=source_doc)
    session.add(q)
    session.commit()
    session.refresh(q)
    return q


def make_decision(session, title="Decisão W", answers_question_id=None):
    d = Decision(title=title, status=DecisionStatus.approved,
                 answers_question_id=answers_question_id)
    session.add(d)
    session.commit()
    session.refresh(d)
    return d


def make_context(session, doc_count=1, last_source_doc="doc1.txt"):
    ctx = AccumulatedContext(
        snapshot_json="{}",
        document_count=doc_count,
        last_source_doc=last_source_doc,
    )
    session.add(ctx)
    session.commit()
    return ctx


# ---------------------------------------------------------------------------
# Testes — Regra 1: orphan_task
# ---------------------------------------------------------------------------

def test_orphan_task_detectado(session):
    project = make_project(session)
    make_task(session, title="Task Sem Dono", status=TaskStatus.orphan, project_id=project.id)

    proposals = run_rules(session)
    orphans = [p for p in proposals if p["type"] == "orphan_task"]

    assert len(orphans) == 1
    assert "Task Sem Dono" in orphans[0]["title"]
    assert orphans[0]["priority"] == "medium"
    assert orphans[0]["entity_type"] == "Task"


def test_orphan_task_nao_dispara_para_task_open(session):
    make_task(session, title="Task Normal", status=TaskStatus.open)
    proposals = run_rules(session)
    assert not any(p["type"] == "orphan_task" for p in proposals)


def test_orphan_task_multiplas(session):
    project = make_project(session)
    make_task(session, title="Orphan 1", status=TaskStatus.orphan, project_id=project.id)
    make_task(session, title="Orphan 2", status=TaskStatus.orphan, project_id=project.id)
    proposals = run_rules(session)
    orphans = [p for p in proposals if p["type"] == "orphan_task"]
    assert len(orphans) == 2


# ---------------------------------------------------------------------------
# Testes — Regra 2: overdue_task
# ---------------------------------------------------------------------------

def test_overdue_task_detectado(session):
    project = make_project(session)
    person = make_person(session, "Bruno")
    task = make_task(session, title="Task Atrasada", status=TaskStatus.overdue, project_id=project.id)
    session.add(TaskPersonLink(task_id=task.id, person_id=person.id))
    session.commit()

    proposals = run_rules(session)
    overdues = [p for p in proposals if p["type"] == "overdue_task"]

    assert len(overdues) == 1
    assert "Bruno" in overdues[0]["description"]
    assert overdues[0]["priority"] == "high"


def test_overdue_task_sem_assignee(session):
    make_task(session, title="Atrasada Sem Dono", status=TaskStatus.overdue)
    proposals = run_rules(session)
    overdues = [p for p in proposals if p["type"] == "overdue_task"]
    assert len(overdues) == 1
    assert "sem responsável" in overdues[0]["description"]


# ---------------------------------------------------------------------------
# Testes — Regra 3: critical_risk
# ---------------------------------------------------------------------------

def test_critical_risk_severity_9(session):
    project = make_project(session)
    make_risk(session, title="Risco Grave", severity=9, status=RiskStatus.open, project_id=project.id)
    proposals = run_rules(session)
    crits = [p for p in proposals if p["type"] == "critical_risk"]
    assert len(crits) == 1
    assert crits[0]["priority"] == "critical"


def test_critical_risk_severity_7(session):
    project = make_project(session)
    make_risk(session, title="Risco Alto", severity=7, status=RiskStatus.critical, project_id=project.id)
    proposals = run_rules(session)
    crits = [p for p in proposals if p["type"] == "critical_risk"]
    assert len(crits) == 1
    assert crits[0]["priority"] == "high"


def test_critical_risk_nao_dispara_severity_baixa(session):
    make_risk(session, title="Risco Baixo", severity=4, status=RiskStatus.open)
    proposals = run_rules(session)
    assert not any(p["type"] == "critical_risk" for p in proposals)


def test_critical_risk_nao_dispara_mitigated(session):
    make_risk(session, title="Risco Mitigado", severity=9, status=RiskStatus.mitigated)
    proposals = run_rules(session)
    assert not any(p["type"] == "critical_risk" for p in proposals)


def test_critical_risk_limiar_exato_severity_6(session):
    """Severity 6 não deve disparar."""
    make_risk(session, title="Risco 6", severity=6, status=RiskStatus.open)
    proposals = run_rules(session)
    assert not any(p["type"] == "critical_risk" for p in proposals)


# ---------------------------------------------------------------------------
# Testes — Regra 4: answered_question
# ---------------------------------------------------------------------------

def test_answered_question_dispara(session):
    question = make_question(session, title="O que fazer?", status=OpenQuestionStatus.open)
    make_decision(session, title="Decidimos X", answers_question_id=question.id)

    proposals = run_rules(session)
    answered = [p for p in proposals if p["type"] == "answered_question"]

    assert len(answered) == 1
    assert "O que fazer?" in answered[0]["title"]
    assert answered[0]["priority"] == "low"


def test_answered_question_nao_dispara_se_ja_answered(session):
    question = make_question(session, title="Já respondida", status=OpenQuestionStatus.answered)
    make_decision(session, title="Decisão", answers_question_id=question.id)

    proposals = run_rules(session)
    assert not any(p["type"] == "answered_question" for p in proposals)


def test_answered_question_nao_dispara_sem_link(session):
    make_decision(session, title="Decisão solta", answers_question_id=None)
    proposals = run_rules(session)
    assert not any(p["type"] == "answered_question" for p in proposals)


# ---------------------------------------------------------------------------
# Testes — Regra 5: spof
# ---------------------------------------------------------------------------

def test_spof_detectado(session):
    project = make_project(session, name="Projeto Solo")
    person = make_person(session, "Carlos")
    session.add(PersonProjectLink(person_id=person.id, project_id=project.id))
    session.commit()

    proposals = run_rules(session)
    spofs = [p for p in proposals if p["type"] == "spof"]

    assert len(spofs) == 1
    assert "Carlos" in spofs[0]["description"]
    assert "Projeto Solo" in spofs[0]["title"]
    assert spofs[0]["priority"] == "high"


def test_spof_nao_dispara_com_dois_membros(session):
    project = make_project(session, name="Projeto Duo")
    p1 = make_person(session, "Diana")
    p2 = make_person(session, "Eduardo")
    session.add(PersonProjectLink(person_id=p1.id, project_id=project.id))
    session.add(PersonProjectLink(person_id=p2.id, project_id=project.id))
    session.commit()

    proposals = run_rules(session)
    assert not any(p["type"] == "spof" for p in proposals)


def test_spof_nao_dispara_projeto_paused(session):
    project = make_project(session, name="Projeto Pausado", status=ProjectStatus.paused)
    person = make_person(session, "Fernanda")
    session.add(PersonProjectLink(person_id=person.id, project_id=project.id))
    session.commit()

    proposals = run_rules(session)
    assert not any(p["type"] == "spof" for p in proposals)


# ---------------------------------------------------------------------------
# Testes — Regra 6: stale_question
# ---------------------------------------------------------------------------

def test_stale_question_detectada(session):
    make_context(session, doc_count=3, last_source_doc="doc3.txt")
    make_question(session, title="Pergunta Velha", status=OpenQuestionStatus.open, source_doc="doc1.txt")

    proposals = run_rules(session)
    stale = [p for p in proposals if p["type"] == "stale_question"]

    assert len(stale) == 1
    assert "Pergunta Velha" in stale[0]["title"]
    assert stale[0]["priority"] == "medium"


def test_stale_question_nao_dispara_se_mesmo_doc(session):
    make_context(session, doc_count=3, last_source_doc="doc3.txt")
    make_question(session, title="Pergunta Recente", status=OpenQuestionStatus.open, source_doc="doc3.txt")

    proposals = run_rules(session)
    assert not any(p["type"] == "stale_question" for p in proposals)


def test_stale_question_nao_dispara_com_1_documento(session):
    make_context(session, doc_count=1, last_source_doc="doc1.txt")
    make_question(session, title="Única Pergunta", status=OpenQuestionStatus.open, source_doc="doc1.txt")

    proposals = run_rules(session)
    assert not any(p["type"] == "stale_question" for p in proposals)


def test_stale_question_nao_dispara_se_answered(session):
    make_context(session, doc_count=3, last_source_doc="doc3.txt")
    make_question(session, title="Já Respondida", status=OpenQuestionStatus.answered, source_doc="doc1.txt")

    proposals = run_rules(session)
    assert not any(p["type"] == "stale_question" for p in proposals)


# ---------------------------------------------------------------------------
# Teste de integração: banco vazio → lista vazia
# ---------------------------------------------------------------------------

def test_banco_vazio_retorna_lista_vazia(session):
    proposals = run_rules(session)
    assert proposals == []


# ---------------------------------------------------------------------------
# Teste de integração: múltiplas regras ao mesmo tempo
# ---------------------------------------------------------------------------

def test_multiplas_regras_simultaneas(session):
    make_context(session, doc_count=2, last_source_doc="doc2.txt")

    project = make_project(session, name="Projeto Caótico")
    person = make_person(session, "Gustavo")
    session.add(PersonProjectLink(person_id=person.id, project_id=project.id))

    make_task(session, title="Task Órfã", status=TaskStatus.orphan, project_id=project.id)
    make_risk(session, title="Risco Explosivo", severity=10, status=RiskStatus.critical, project_id=project.id)
    question = make_question(session, title="Pergunta Antiga", source_doc="doc1.txt")
    make_decision(session, title="Decisão Final", answers_question_id=question.id)
    session.commit()

    proposals = run_rules(session)
    types = {p["type"] for p in proposals}

    assert "orphan_task" in types
    assert "critical_risk" in types
    assert "spof" in types
    assert "stale_question" in types
    assert "answered_question" in types