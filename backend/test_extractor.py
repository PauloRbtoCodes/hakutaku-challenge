# backend/test_extractor.py

import json
import pytest
from unittest.mock import patch, MagicMock
from backend.extractor import run_extraction, _extract_json

# ── documento de teste ─────────────────────────────────────────────────────────

FAKE_DOCUMENT = """
Reunião de planejamento — Projeto Alpha — 2025-03-28

Participantes: Ana Lima (tech lead), Bruno Souza (dev), Carla Mendes (PM)

Decisões:
- Aprovado o uso de FastAPI como framework principal (responde à dúvida levantada na semana passada sobre qual framework adotar)
- Bruno ficará responsável pela task de configurar o CI/CD até 2025-04-05

Riscos identificados:
- Risco de atraso na entrega por dependência externa de API de pagamento (severidade 8)

Perguntas em aberto:
- Como vamos monitorar os logs em produção?

Ana vai liderar o módulo de autenticação, sem prazo definido ainda.
"""

# ── mocks de resposta do LLM ───────────────────────────────────────────────────

MOCK_PROMPT1_RESPONSE = json.dumps({
    "projects": [{"name": "Alpha", "status": "active", "description": "Projeto principal"}],
    "persons": [
        {"name": "Ana Lima", "aliases": [], "role": "tech lead", "status": "active"},
        {"name": "Bruno Souza", "aliases": [], "role": "dev", "status": "active"},
        {"name": "Carla Mendes", "aliases": [], "role": "PM", "status": "active"},
    ],
    "tasks": [
        {"title": "Configurar CI/CD", "status": "open", "deadline": "2025-04-05", "priority": "high", "project_name": "Alpha", "assignee_names": ["Bruno Souza"]},
        {"title": "Módulo de autenticação", "status": "open", "deadline": None, "priority": "medium", "project_name": "Alpha", "assignee_names": ["Ana Lima"]},
    ],
    "risks": [
        {"title": "Atraso por dependência de API de pagamento", "status": "open", "severity": 8, "project_name": "Alpha"}
    ],
    "decisions": [
        {"title": "Uso de FastAPI como framework principal", "status": "approved", "decided_by": "Carla Mendes", "answers_question_title": "Qual framework adotar"}
    ],
    "open_questions": [
        {"title": "Como monitorar logs em produção", "status": "open", "asked_by": None},
        {"title": "Qual framework adotar", "status": "open", "asked_by": None},
    ],
})

MOCK_PROMPT2_RESPONSE = json.dumps({
    "relations": [
        {"from_type": "Task", "from_title": "Configurar CI/CD", "relation": "belongs_to", "to_type": "Project", "to_title": "Alpha"},
        {"from_type": "Task", "from_title": "Configurar CI/CD", "relation": "assigned_to", "to_type": "Person", "to_title": "Bruno Souza"},
        {"from_type": "Task", "from_title": "Módulo de autenticação", "relation": "belongs_to", "to_type": "Project", "to_title": "Alpha"},
        {"from_type": "Task", "from_title": "Módulo de autenticação", "relation": "assigned_to", "to_type": "Person", "to_title": "Ana Lima"},
        {"from_type": "Risk", "from_title": "Atraso por dependência de API de pagamento", "relation": "threatens", "to_type": "Project", "to_title": "Alpha"},
        {"from_type": "Decision", "from_title": "Uso de FastAPI como framework principal", "relation": "answers", "to_type": "OpenQuestion", "to_title": "Qual framework adotar"},
        {"from_type": "Person", "from_title": "Ana Lima", "relation": "member_of", "to_type": "Project", "to_title": "Alpha"},
        {"from_type": "Person", "from_title": "Bruno Souza", "relation": "member_of", "to_type": "Project", "to_title": "Alpha"},
    ]
})


# ── fixture: mock do LLM + banco ──────────────────────────────────────────────

def _make_llm_mock(call_count_holder):
    """Retorna respostas alternadas: primeira chamada = Prompt1, segunda = Prompt2."""
    def fake_call_llm(prompt, max_tokens=4096):
        call_count_holder["n"] += 1
        return MOCK_PROMPT1_RESPONSE if call_count_holder["n"] == 1 else MOCK_PROMPT2_RESPONSE
    return fake_call_llm


# ── testes ─────────────────────────────────────────────────────────────────────

class TestExtractJson:
    def test_sem_fence(self):
        raw = '{"a": 1}'
        assert _extract_json(raw) == '{"a": 1}'

    def test_com_fence_json(self):
        raw = '```json\n{"a": 1}\n```'
        assert _extract_json(raw) == '{"a": 1}'

    def test_com_fence_simples(self):
        raw = '```\n{"a": 1}\n```'
        assert _extract_json(raw) == '{"a": 1}'

    def test_com_espaco_extra(self):
        raw = '  ```json\n{"a": 1}\n```  '
        assert _extract_json(raw) == '{"a": 1}'


class TestRunExtraction:

    def _run(self):
        counter = {"n": 0}
        with patch("backend.extractor._call_llm", side_effect=_make_llm_mock(counter)), \
             patch("backend.extractor.load_latest_context", return_value=None), \
             patch("backend.extractor.build_context_block", return_value="## Contexto acumulado\nNenhum contexto anterior disponível."), \
             patch("backend.extractor.persist_extraction", return_value=None):
            return run_extraction(FAKE_DOCUMENT, source_doc="reuniao_alpha_2025-03-28.txt")

    # contagens
    def test_projects_extraidos(self):
        result = self._run()
        assert len(result["extraction"]["projects"]) == 1

    def test_persons_extraidos(self):
        result = self._run()
        assert len(result["extraction"]["persons"]) == 3

    def test_tasks_extraidas(self):
        result = self._run()
        assert len(result["extraction"]["tasks"]) == 2

    def test_risks_extraidos(self):
        result = self._run()
        assert len(result["extraction"]["risks"]) == 1

    def test_decisions_extraidas(self):
        result = self._run()
        assert len(result["extraction"]["decisions"]) == 1

    def test_open_questions_extraidas(self):
        result = self._run()
        assert len(result["extraction"]["open_questions"]) == 2

    # relações
    def test_relacoes_count(self):
        result = self._run()
        assert len(result["relations"]) == 8

    def test_relacao_decision_answers_question(self):
        result = self._run()
        answers_rels = [r for r in result["relations"] if r["relation"] == "answers"]
        assert len(answers_rels) == 1
        assert answers_rels[0]["from_title"] == "Uso de FastAPI como framework principal"
        assert answers_rels[0]["to_title"] == "Qual framework adotar"

    def test_relacao_risk_threatens_project(self):
        result = self._run()
        threatens = [r for r in result["relations"] if r["relation"] == "threatens"]
        assert len(threatens) == 1
        assert threatens[0]["to_title"] == "Alpha"

    def test_task_com_assignee_nao_eh_orphan(self):
        result = self._run()
        tasks = result["extraction"]["tasks"]
        cicd = next(t for t in tasks if "CI/CD" in t.title)
        assert cicd.status != "orphan"

    def test_source_doc_retornado(self):
        result = self._run()
        assert result["source_doc"] == "reuniao_alpha_2025-03-28.txt"

    def test_sem_parse_errors(self):
        result = self._run()
        assert result["parse_errors"] == 0

    # erro proposital
    def test_json_invalido_no_prompt1_lanca_erro(self):
        with patch("backend.extractor._call_llm", return_value="isso não é json"), \
             patch("backend.extractor.load_latest_context", return_value=None), \
             patch("backend.extractor.build_context_block", return_value=""), \
             patch("backend.extractor.persist_extraction", return_value=None):
            with pytest.raises(ValueError, match="Prompt 1 retornou JSON inválido"):
                run_extraction(FAKE_DOCUMENT, source_doc="teste_erro.txt")