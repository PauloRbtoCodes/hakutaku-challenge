"""
test_database.py — Smoke test para database.py
Roda sem API key, sem extractor. Banco em memória, zero side effects.

Execute na raiz do projeto:
    python backend/test_database.py

Cada bloco imprime ✅ PASS ou ❌ FAIL com o motivo.
"""

import json
import os
import sys

# Banco em memória — não polui hakutaku.db
os.environ["DATABASE_URL"] = "sqlite://"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Patch do engine ANTES de importar database.py
import sqlmodel
from sqlmodel import create_engine
_mem_engine = create_engine("sqlite://", echo=False)

import backend.database as db_module
db_module.engine = _mem_engine  # substitui engine antes de qualquer uso

from sqlmodel import Session, select
from backend.database import (
    _apply_relations,
    _update_accumulated_context,
    build_context_block,
    init_db,
    load_latest_context,
    persist_extraction,
)
from backend.models import (
    AccumulatedContext,
    Decision,
    DecisionStatus,
    OpenQuestion,
    OpenQuestionStatus,
    Person,
    PersonProjectLink,
    PersonStatus,
    Project,
    ProjectStatus,
    Risk,
    RiskStatus,
    Task,
    TaskPersonLink,
    TaskStatus,
)

# ---------------------------------------------------------------------------
# Infra mínima de asserção
# ---------------------------------------------------------------------------

results: list[tuple[str, bool, str]] = []

def check(name: str, condition: bool, detail: str = "") -> None:
    mark = "✅ PASS" if condition else "❌ FAIL"
    results.append((name, condition, detail))
    suffix = f"\n         → {detail}" if (not condition and detail) else ""
    print(f"  {mark}  {name}{suffix}")

def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")

def fresh_session():
    return Session(_mem_engine)

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

section("Setup")
init_db()
check("init_db() sem erro", True)

# ---------------------------------------------------------------------------
# Teste 1 — INSERT básico de todas as entidades
# ---------------------------------------------------------------------------

section("Teste 1 — INSERT: todos os tipos de entidade")

proj = Project(name="CRM Integration", status=ProjectStatus.active, description="Integração com Salesforce")
person = Person(name="Marina Costa", role="Backend Engineer", status=PersonStatus.active)
task_orphan = Task(title="Configurar ambiente de staging", status=TaskStatus.open)
task_orphan.__dict__["_project_name"] = "CRM Integration"
task_orphan.__dict__["_assignee_names"] = []  # sem dono → orphan

task_assigned = Task(title="Criar schema de mapeamento", status=TaskStatus.open, deadline="2025-03-28")
task_assigned.__dict__["_project_name"] = "CRM Integration"
task_assigned.__dict__["_assignee_names"] = ["Marina Costa"]

risk = Risk(title="TechNova pode cancelar contrato", status=RiskStatus.open, severity=8)
risk.__dict__["_project_name"] = "CRM Integration"

oq = OpenQuestion(title="REST API ou GraphQL para integração?", status=OpenQuestionStatus.open, asked_by="Marina Costa")

dec = Decision(title="Usar REST API, não GraphQL", status=DecisionStatus.approved, decided_by="João Silva")
dec.__dict__["_answers_question_title"] = "REST API ou GraphQL para integração?"

extraction_1 = {
    "projects":       [proj],
    "persons":        [person],
    "tasks":          [task_orphan, task_assigned],
    "risks":          [risk],
    "decisions":      [dec],
    "open_questions": [oq],
}
relations_1: list[dict] = []

persist_extraction(extraction_1, relations_1, source_doc="reuniao_1.txt")

with fresh_session() as s:
    check("Project inserido",      s.exec(select(Project).where(Project.name == "CRM Integration")).first() is not None)
    check("Person inserida",       s.exec(select(Person).where(Person.name == "Marina Costa")).first() is not None)
    check("Risk inserido",         s.exec(select(Risk).where(Risk.title == "TechNova pode cancelar contrato")).first() is not None)
    check("OpenQuestion inserida", s.exec(select(OpenQuestion).where(OpenQuestion.title == "REST API ou GraphQL para integração?")).first() is not None)
    check("Decision inserida",     s.exec(select(Decision).where(Decision.title == "Usar REST API, não GraphQL")).first() is not None)

    tasks_db = s.exec(select(Task)).all()
    check("2 Tasks inseridas", len(tasks_db) == 2, f"encontradas: {len(tasks_db)}")

# ---------------------------------------------------------------------------
# Teste 2 — orphan automático (task sem assignee)
# ---------------------------------------------------------------------------

section("Teste 2 — Task sem assignee vira orphan")

with fresh_session() as s:
    t = s.exec(select(Task).where(Task.title == "Configurar ambiente de staging")).first()
    check("Task orphan com status=orphan", t is not None and t.status == TaskStatus.orphan,
          f"status atual: {t.status if t else 'não encontrada'}")

# ---------------------------------------------------------------------------
# Teste 3 — FK resolvida: Task → Project
# ---------------------------------------------------------------------------

section("Teste 3 — FK: Task → Project")

with fresh_session() as s:
    proj_db = s.exec(select(Project).where(Project.name == "CRM Integration")).first()
    task_db = s.exec(select(Task).where(Task.title == "Criar schema de mapeamento")).first()
    check("Task tem project_id correto",
          task_db is not None and task_db.project_id == proj_db.id,
          f"task.project_id={task_db.project_id if task_db else '?'}, proj.id={proj_db.id if proj_db else '?'}")

# ---------------------------------------------------------------------------
# Teste 4 — FK resolvida: Task → Person (TaskPersonLink)
# ---------------------------------------------------------------------------

section("Teste 4 — FK: Task → Person (assigned_to)")

with fresh_session() as s:
    task_db = s.exec(select(Task).where(Task.title == "Criar schema de mapeamento")).first()
    person_db = s.exec(select(Person).where(Person.name == "Marina Costa")).first()
    link = s.exec(
        select(TaskPersonLink).where(
            TaskPersonLink.task_id == task_db.id,
            TaskPersonLink.person_id == person_db.id,
        )
    ).first() if task_db and person_db else None
    check("TaskPersonLink criado", link is not None)

# ---------------------------------------------------------------------------
# Teste 5 — FK resolvida: Risk → Project
# ---------------------------------------------------------------------------

section("Teste 5 — FK: Risk → Project")

with fresh_session() as s:
    proj_db = s.exec(select(Project).where(Project.name == "CRM Integration")).first()
    risk_db = s.exec(select(Risk).where(Risk.title == "TechNova pode cancelar contrato")).first()
    check("Risk tem project_id correto",
          risk_db is not None and risk_db.project_id == proj_db.id,
          f"risk.project_id={risk_db.project_id if risk_db else '?'}")

# ---------------------------------------------------------------------------
# Teste 6 — Momento "uau": Decision → answers → OpenQuestion
# ---------------------------------------------------------------------------

section("Teste 6 — Momento 'uau': Decision responde OpenQuestion")

with fresh_session() as s:
    dec_db = s.exec(select(Decision).where(Decision.title == "Usar REST API, não GraphQL")).first()
    oq_db  = s.exec(select(OpenQuestion).where(OpenQuestion.title == "REST API ou GraphQL para integração?")).first()

    check("Decision tem answers_question_id",
          dec_db is not None and dec_db.answers_question_id is not None,
          f"answers_question_id={dec_db.answers_question_id if dec_db else '?'}")
    check("OpenQuestion marcada como answered",
          oq_db is not None and oq_db.status == OpenQuestionStatus.answered,
          f"status atual: {oq_db.status if oq_db else '?'}")
    check("FK aponta para a pergunta certa",
          dec_db is not None and oq_db is not None and dec_db.answers_question_id == oq_db.id)

# ---------------------------------------------------------------------------
# Teste 7 — UPDATE_STATE: Risk escala open → critical
# ---------------------------------------------------------------------------

section("Teste 7 — UPDATE_STATE: Risk open → critical")

risk_v2 = Risk(title="TechNova pode cancelar contrato", status=RiskStatus.critical, severity=9)
risk_v2.__dict__["_project_name"] = "CRM Integration"

persist_extraction({"projects": [], "persons": [], "tasks": [], "risks": [risk_v2],
                    "decisions": [], "open_questions": []}, [], "reuniao_2.txt")

with fresh_session() as s:
    risk_db = s.exec(select(Risk).where(Risk.title == "TechNova pode cancelar contrato")).first()
    check("Risk escalou para critical", risk_db is not None and risk_db.status == RiskStatus.critical,
          f"status: {risk_db.status if risk_db else '?'}")
    check("Severity subiu para 9", risk_db is not None and risk_db.severity == 9,
          f"severity: {risk_db.severity if risk_db else '?'}")

# ---------------------------------------------------------------------------
# Teste 8 — UPDATE_STATE: Risk crítico NÃO desce com novo doc dizendo "open"
# ---------------------------------------------------------------------------

section("Teste 8 — UPDATE_STATE: Risk crítico não regride para open")

risk_v3 = Risk(title="TechNova pode cancelar contrato", status=RiskStatus.open, severity=5)
risk_v3.__dict__["_project_name"] = "CRM Integration"

persist_extraction({"projects": [], "persons": [], "tasks": [], "risks": [risk_v3],
                    "decisions": [], "open_questions": []}, [], "chat_25mar.txt")

with fresh_session() as s:
    risk_db = s.exec(select(Risk).where(Risk.title == "TechNova pode cancelar contrato")).first()
    check("Risk crítico não regrediu para open",
          risk_db is not None and risk_db.status == RiskStatus.critical,
          f"status: {risk_db.status if risk_db else '?'}")

# ---------------------------------------------------------------------------
# Teste 9 — ENRICH: Person ganha role em doc posterior
# ---------------------------------------------------------------------------

section("Teste 9 — ENRICH: Person ganha role")

pedro = Person(name="Pedro Almeida", status=PersonStatus.active)  # sem role
pedro.__dict__["_project_names"] = ["CRM Integration"]

persist_extraction({"projects": [], "persons": [pedro], "tasks": [], "risks": [],
                    "decisions": [], "open_questions": []}, [], "reuniao_1.txt")

with fresh_session() as s:
    p = s.exec(select(Person).where(Person.name == "Pedro Almeida")).first()
    check("Pedro inserido sem role", p is not None and p.role is None, f"role: {p.role if p else '?'}")

pedro_com_role = Person(name="Pedro Almeida", role="Product Manager", status=PersonStatus.active)
pedro_com_role.__dict__["_project_names"] = ["CRM Integration"]

persist_extraction({"projects": [], "persons": [pedro_com_role], "tasks": [], "risks": [],
                    "decisions": [], "open_questions": []}, [], "reuniao_2.txt")

with fresh_session() as s:
    p = s.exec(select(Person).where(Person.name == "Pedro Almeida")).first()
    check("Pedro enriquecido com role", p is not None and p.role == "Product Manager",
          f"role: {p.role if p else '?'}")

# ---------------------------------------------------------------------------
# Teste 10 — _apply_relations: orphan vira open quando assignee chega via Prompt 2
# ---------------------------------------------------------------------------

section("Teste 10 — _apply_relations: orphan → open via relação do Prompt 2")

# staging task ainda é orphan — vai receber assignee via relação
with fresh_session() as s:
    t = s.exec(select(Task).where(Task.title == "Configurar ambiente de staging")).first()
    check("Task staging ainda é orphan antes da relação", t is not None and t.status == TaskStatus.orphan)

# Lucas ainda não existe — será criado implicitamente? Não: _apply_relations não cria pessoas.
# Então primeiro garantimos que Lucas existe.
lucas = Person(name="Lucas Mendes", status=PersonStatus.active)
lucas.__dict__["_project_names"] = []
persist_extraction({"projects": [], "persons": [lucas], "tasks": [], "risks": [],
                    "decisions": [], "open_questions": []}, [], "chat.txt")

relations_prompt2 = [
    {
        "from_type": "Task",
        "from_title": "Configurar ambiente de staging",
        "relation": "assigned_to",
        "to_type": "Person",
        "to_title": "Lucas Mendes",
    }
]

with fresh_session() as s:
    _apply_relations(s, relations_prompt2)
    s.commit()

with fresh_session() as s:
    t = s.exec(select(Task).where(Task.title == "Configurar ambiente de staging")).first()
    check("Task staging saiu de orphan para open",
          t is not None and t.status == TaskStatus.open,
          f"status: {t.status if t else '?'}")
    lucas_db = s.exec(select(Person).where(Person.name == "Lucas Mendes")).first()
    link = s.exec(
        select(TaskPersonLink).where(
            TaskPersonLink.task_id == t.id,
            TaskPersonLink.person_id == lucas_db.id,
        )
    ).first() if t and lucas_db else None
    check("TaskPersonLink criado para Lucas", link is not None)

# ---------------------------------------------------------------------------
# Teste 11 — AccumulatedContext salvo e load_latest_context funciona
# ---------------------------------------------------------------------------

section("Teste 11 — AccumulatedContext e load_latest_context")

ctx = load_latest_context()
check("load_latest_context retorna dict", ctx is not None and isinstance(ctx, dict))
check("snapshot tem chave 'projects'", ctx is not None and "projects" in ctx)
check("snapshot tem chave 'persons'",  ctx is not None and "persons" in ctx)
check("snapshot tem document_count",   ctx is not None and ctx.get("document_count", 0) > 0,
      f"document_count={ctx.get('document_count') if ctx else '?'}")

# ---------------------------------------------------------------------------
# Teste 12 — build_context_block gera texto coerente
# ---------------------------------------------------------------------------

section("Teste 12 — build_context_block")

block = build_context_block(ctx)
check("build_context_block retorna string não vazia", isinstance(block, str) and len(block) > 50)
check("Contém seção de projetos",  "Projetos conhecidos" in block)
check("Contém seção de pessoas",   "Pessoas conhecidas" in block)
check("Risk crítico aparece no bloco", "TechNova" in block,
      "Risk mitigated/dismissed seria filtrado — crítico deve aparecer")
check("Perguntas respondidas NÃO aparecem",
      "REST API ou GraphQL" not in block,
      "OpenQuestion answered deve ser filtrada do bloco de contexto")

block_none = build_context_block(None)
check("build_context_block(None) retorna texto de primeiro documento",
      "Primeiro documento" in block_none or "nenhum contexto" in block_none.lower())

# ---------------------------------------------------------------------------
# Resumo
# ---------------------------------------------------------------------------

total  = len(results)
passed = sum(1 for _, ok, _ in results if ok)
failed = total - passed

print(f"\n{'═' * 60}")
print(f"  Resultado: {passed}/{total} testes passaram", end="")
if failed:
    print(f"  ({failed} falharam)")
    print("\n  Falhas:")
    for name, ok, detail in results:
        if not ok:
            print(f"    ❌ {name}" + (f" → {detail}" if detail else ""))
else:
    print(" 🎉")
print(f"{'═' * 60}\n")

sys.exit(0 if failed == 0 else 1)
