# backend/parsers.py
# =============================================================================
# Parsers: traduzem o JSON bruto do LLM em objetos Python (modelos SQLModel)
# O LLM é otimista — pode mandar campos errados, faltando ou com tipos trocados.
# Esses parsers são defensivos: normalizam tudo antes de tocar no banco.
# =============================================================================

from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from backend.models import (
    Task, TaskStatus,
    Risk, RiskStatus,
    Decision, DecisionStatus,
    OpenQuestion, OpenQuestionStatus,
    Person, PersonStatus,
    Project, ProjectStatus,
)

logger = logging.getLogger(__name__)


# =============================================================================
# HELPERS
# =============================================================================

def _str(value: Any, fallback: str = "") -> str:
    """Garante string, nunca None."""
    if value is None:
        return fallback
    return str(value).strip()


def _int_clamp(value: Any, min_val: int, max_val: int, fallback: int) -> int:
    """Converte para int e mantém dentro do range."""
    try:
        result = int(value)
        return max(min_val, min(max_val, result))
    except (TypeError, ValueError):
        return fallback


def _enum_safe(enum_class, value: Any, fallback):
    """
    Converte string para Enum de forma segura.
    Se o LLM mandar um valor inválido, usa o fallback sem explodir.
    """
    try:
        return enum_class(str(value).lower())
    except ValueError:
        logger.warning(
            f"Valor inválido '{value}' para {enum_class.__name__}. "
            f"Usando fallback: {fallback}"
        )
        return fallback


def _parse_aliases(value: Any) -> Optional[str]:
    """
    Aliases podem vir como lista Python ou string JSON.
    Sempre salva como JSON string no banco.
    """
    if value is None:
        return None
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            # Veio como string simples, transforma em lista de um item
            return json.dumps([value], ensure_ascii=False)
    return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


# =============================================================================
# PARSERS INDIVIDUAIS — um por entidade
# =============================================================================

def parse_project(data: dict, source_doc: str = "") -> Optional[Project]:
    """
    Espera:
    {
        "name": "Integração CRM",
        "status": "active",          # opcional
        "description": "..."         # opcional
    }
    """
    name = _str(data.get("name"))
    if not name:
        logger.warning(f"Project sem nome ignorado: {data}")
        return None

    return Project(
        name        = name,
        status      = _enum_safe(ProjectStatus, data.get("status"), ProjectStatus.active),
        description = _str(data.get("description")) or None,
        source_doc  = source_doc,
        created_at  = _now(),
        updated_at  = _now(),
    )


def parse_person(data: dict, source_doc: str = "") -> Optional[Person]:
    """
    Espera:
    {
        "name": "Marina Costa",
        "aliases": ["marina.costa", "Marina"],   # opcional
        "role": "engenheira de backend",         # opcional
        "status": "active"                       # opcional
    }
    """
    name = _str(data.get("name"))
    if not name:
        logger.warning(f"Person sem nome ignorado: {data}")
        return None

    return Person(
        name       = name,
        aliases    = _parse_aliases(data.get("aliases")),
        role       = _str(data.get("role")) or None,
        status     = _enum_safe(PersonStatus, data.get("status"), PersonStatus.active),
        source_doc = source_doc,
        created_at = _now(),
        updated_at = _now(),
    )


def parse_task(data: dict, source_doc: str = "") -> Optional[Task]:
    """
    Espera:
    {
        "title": "Criar schema de mapeamento",
        "description": "...",         # opcional
        "status": "open",             # opcional, default: open
        "deadline": "2025-03-28",     # opcional, ISO 8601
        "priority": "high",           # opcional: low | normal | high | critical
        "project_name": "Integração CRM",   # opcional, resolvido depois em database.py
        "assignee_names": ["Marina Costa"]  # opcional, lista de nomes canônicos
    }

    Nota: project_id e assignees NÃO são setados aqui.
    A reconciliação com o banco (quem é quem) acontece em database.py.
    O parser só valida e estrutura — não faz queries.
    """
    title = _str(data.get("title"))
    if not title:
        logger.warning(f"Task sem título ignorada: {data}")
        return None

    # Se não tem assignee_names → status orphan automaticamente
    assignee_names = data.get("assignee_names") or []
    if isinstance(assignee_names, str):
        assignee_names = [assignee_names]

    status_raw = data.get("status")
    if not assignee_names and not status_raw:
        status = TaskStatus.orphan
    else:
        status = _enum_safe(TaskStatus, status_raw, TaskStatus.open)

    task = Task(
        title       = title,
        description = _str(data.get("description")) or None,
        status      = status,
        deadline    = _str(data.get("deadline")) or None,
        priority    = _str(data.get("priority")) or None,
        source_doc  = source_doc,
        created_at  = _now(),
        updated_at  = _now(),
    )

    # Metadados temporários para database.py resolver depois
    task.__dict__["_project_name"]   = _str(data.get("project_name")) or None
    task.__dict__["_assignee_names"] = assignee_names

    return task


def parse_risk(data: dict, source_doc: str = "") -> Optional[Risk]:
    """
    Espera:
    {
        "title": "TechNova pode cancelar contrato",
        "description": "...",         # opcional
        "status": "open",             # opcional
        "severity": 8,                # opcional, 1–10
        "project_name": "Integração CRM"  # opcional
    }
    """
    title = _str(data.get("title"))
    if not title:
        logger.warning(f"Risk sem título ignorado: {data}")
        return None

    risk = Risk(
        title       = title,
        description = _str(data.get("description")) or None,
        status      = _enum_safe(RiskStatus, data.get("status"), RiskStatus.open),
        severity    = _int_clamp(data.get("severity"), 1, 10, 5),
        source_doc  = source_doc,
        created_at  = _now(),
        updated_at  = _now(),
    )

    # Metadado temporário para database.py resolver depois (igual a Task e Decision)
    risk.__dict__["_project_name"] = _str(data.get("project_name")) or None

    return risk


def parse_decision(data: dict, source_doc: str = "") -> Optional[Decision]:
    """
    Espera:
    {
        "title": "Usar REST API, não GraphQL",
        "description": "...",              # opcional
        "status": "approved",              # opcional
        "decided_by": "João Silva",        # opcional
        "answers_question_title": "REST vs GraphQL?"  # opcional — o momento "uau"
    }

    answers_question_title é o texto da OpenQuestion que esta Decision responde.
    database.py vai fazer o match pelo título e setar answers_question_id.
    """
    title = _str(data.get("title"))
    if not title:
        logger.warning(f"Decision sem título ignorada: {data}")
        return None

    decision = Decision(
        title       = title,
        description = _str(data.get("description")) or None,
        status      = _enum_safe(DecisionStatus, data.get("status"), DecisionStatus.approved),
        decided_by  = _str(data.get("decided_by")) or None,
        source_doc  = source_doc,
        created_at  = _now(),
        updated_at  = _now(),
    )

    # Metadado temporário: título da OpenQuestion que esta Decision responde
    decision.__dict__["_answers_question_title"] = (
        _str(data.get("answers_question_title")) or None
    )

    return decision


def parse_open_question(data: dict, source_doc: str = "") -> Optional[OpenQuestion]:
    """
    Espera:
    {
        "title": "REST API ou GraphQL para integração?",
        "description": "...",    # opcional
        "status": "open",        # opcional
        "asked_by": "Marina Costa"  # opcional
    }
    """
    title = _str(data.get("title"))
    if not title:
        logger.warning(f"OpenQuestion sem título ignorada: {data}")
        return None

    return OpenQuestion(
        title       = title,
        description = _str(data.get("description")) or None,
        status      = _enum_safe(OpenQuestionStatus, data.get("status"), OpenQuestionStatus.open),
        asked_by    = _str(data.get("asked_by")) or None,
        source_doc  = source_doc,
        created_at  = _now(),
        updated_at  = _now(),
    )


# =============================================================================
# PARSER PRINCIPAL — recebe o JSON completo do LLM e parseia tudo de uma vez
# =============================================================================

def parse_extraction_result(
    raw_json: str | dict,
    source_doc: str = "",
) -> dict:
    """
    Recebe o output completo do Prompt 1 (extração de entidades) e retorna
    um dicionário com listas de objetos SQLModel prontos para reconciliação.

    Formato esperado do LLM:
    {
        "projects":       [ { "name": "...", ... } ],
        "persons":        [ { "name": "...", ... } ],
        "tasks":          [ { "title": "...", ... } ],
        "risks":          [ { "title": "...", ... } ],
        "decisions":      [ { "title": "...", ... } ],
        "open_questions": [ { "title": "...", ... } ]
    }

    Retorna:
    {
        "projects":       [Project, ...],
        "persons":        [Person, ...],
        "tasks":          [Task, ...],
        "risks":          [Risk, ...],
        "decisions":      [Decision, ...],
        "open_questions": [OpenQuestion, ...],
        "parse_errors":   int   # quantas entidades foram descartadas
    }
    """
    # Aceita string JSON ou dict
    if isinstance(raw_json, str):
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            logger.error(f"JSON inválido do LLM: {e}")
            return _empty_result()
    else:
        data = raw_json

    errors = 0

    def _parse_list(key, parser_fn):
        nonlocal errors
        results = []
        for item in data.get(key, []):
            try:
                obj = parser_fn(item, source_doc)
                if obj is not None:
                    results.append(obj)
                else:
                    errors += 1
            except Exception as e:
                logger.error(f"Erro ao parsear {key}: {e} | item: {item}")
                errors += 1
        return results

    return {
        "projects":       _parse_list("projects",       parse_project),
        "persons":        _parse_list("persons",        parse_person),
        "tasks":          _parse_list("tasks",          parse_task),
        "risks":          _parse_list("risks",          parse_risk),
        "decisions":      _parse_list("decisions",      parse_decision),
        "open_questions": _parse_list("open_questions", parse_open_question),
        "parse_errors":   errors,
    }


def _empty_result() -> dict:
    return {
        "projects": [], "persons": [], "tasks": [],
        "risks": [], "decisions": [], "open_questions": [],
        "parse_errors": 0,
    }


# =============================================================================
# PARSER DE RELAÇÕES — recebe o output do Prompt 2 (resolução de relações)
# =============================================================================

def parse_relations_result(raw_json: str | dict) -> list[dict]:
    """
    Recebe o output do Prompt 2 e retorna lista de relações estruturadas.

    Formato esperado do LLM:
    {
        "relations": [
            {
                "from_type":  "Decision",
                "from_title": "Usar REST API",
                "relation":   "answers",
                "to_type":    "OpenQuestion",
                "to_title":   "REST vs GraphQL?"
            },
            ...
        ]
    }

    Retorna lista de dicts validados. database.py faz o match por título.
    """
    if isinstance(raw_json, str):
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as e:
            logger.error(f"JSON de relações inválido: {e}")
            return []
    else:
        data = raw_json

    valid_relations = []
    VALID_TYPES = {"Task", "Risk", "Decision", "OpenQuestion", "Person", "Project"}
    VALID_RELATIONS = {"belongs_to", "assigned_to", "threatens", "answers", "member_of"}

    for rel in data.get("relations", []):
        from_type  = _str(rel.get("from_type"))
        from_title = _str(rel.get("from_title"))
        relation   = _str(rel.get("relation"))
        to_type    = _str(rel.get("to_type"))
        to_title   = _str(rel.get("to_title"))

        if not all([from_type, from_title, relation, to_type, to_title]):
            logger.warning(f"Relação incompleta ignorada: {rel}")
            continue

        if from_type not in VALID_TYPES or to_type not in VALID_TYPES:
            logger.warning(f"Tipo de entidade inválido na relação: {rel}")
            continue

        if relation not in VALID_RELATIONS:
            logger.warning(f"Tipo de relação inválido '{relation}': {rel}")
            continue

        valid_relations.append({
            "from_type":  from_type,
            "from_title": from_title,
            "relation":   relation,
            "to_type":    to_type,
            "to_title":   to_title,
        })

    return valid_relations