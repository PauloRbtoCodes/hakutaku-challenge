# backend/prompt_templates.py
# =============================================================================
# Templates dos prompts LLM usados no pipeline de extração.
# Separados do extractor.py para versionamento explícito e auditabilidade.
# Os templates são f-strings: variáveis entre {chaves}.
# =============================================================================

import json


# =============================================================================
# PROMPT 1 — Extração de entidades
# =============================================================================
# Responsabilidade: dado um documento em texto livre, identificar e estruturar
# todas as entidades organizacionais relevantes.
#
# Decisão de design: o contexto acumulado é injetado aqui com instruções
# explícitas de USO — não apenas como referência, mas como âncora para
# deduplicação, evolução de status e resolução de ambiguidades.
# =============================================================================

PROMPT1_TEMPLATE = """\
Você é um extrator de entidades organizacionais especializado em análise de conhecimento corporativo.

{context_block}

---
## INSTRUÇÕES SOBRE O CONTEXTO ACUMULADO
Se houver contexto acumulado acima, aplique rigorosamente:

1. **Deduplicação**: se um Project, Person, Task, Risk, Decision ou OpenQuestion já existir no contexto com nome/título igual ou muito semelhante, extraia-o com o **nome exato do contexto** para que o sistema faça a fusão automática. NÃO crie entidade nova para algo que já existe.

2. **Evolução de status e severidade**: se este documento altera o estado de uma entidade já existente (ex: risco que era "open" passa a "critical"; severity que era 7 agora é 9), use o **novo estado/valor mais alto**. O sistema nunca reduz severidade automaticamente.

3. **Resolução de ambiguidades**: use o contexto para resolver referências vagas ("o projeto" → nome exato do projeto ativo; "ela" → nome completo da Person relevante do contexto).

4. **Perguntas respondidas**: se uma Decision neste documento responde claramente uma OpenQuestion do contexto, preencha `answers_question_title` com o **título exato da pergunta do contexto**.

5. **Pessoas conhecidas**: se uma pessoa do contexto tiver role definida e este documento não alterar isso, preserve o role do contexto.

---
## TIPO DE DOCUMENTO
{doc_type_hint}

---
## Documento a analisar
{document_text}

---
## Schema de extração

Valores válidos:
- Project.status : active | paused | done
- Person.status  : active | inactive
- Task.status    : open | in_progress | done | overdue | orphan
- Risk.status    : open | critical | mitigated | dismissed
- Risk.severity  : inteiro de 1 a 10 (use a severidade MAIS ALTA mencionada)
- Decision.status: proposed | approved | reversed
- OpenQuestion.status: open | answered | dropped
- Task.priority  : low | normal | high | critical

Regras adicionais:
- Task sem assignee → assignee_names: [] (o sistema marca como `orphan` automaticamente)
- Task com assignee definido → status mínimo `open`, não `orphan`
- Use null para campos opcionais desconhecidos

Responda APENAS com JSON válido, sem texto adicional, sem markdown:
{{
  "projects":       [{{"name": "...", "status": "active", "description": null}}],
  "persons":        [{{"name": "...", "aliases": [], "role": null, "status": "active"}}],
  "tasks":          [{{"title": "...", "status": "open", "deadline": null, "priority": "normal", "project_name": null, "assignee_names": []}}],
  "risks":          [{{"title": "...", "status": "open", "severity": 5, "project_name": null}}],
  "decisions":      [{{"title": "...", "status": "approved", "decided_by": null, "answers_question_title": null}}],
  "open_questions": [{{"title": "...", "status": "open", "asked_by": null}}]
}}\
"""


# =============================================================================
# PROMPT 2 — Resolução de relações
# =============================================================================
# Responsabilidade: dado o conjunto de entidades já extraídas e o documento
# original, identificar todas as relações válidas entre as entidades.
#
# Decisão de design: executado APÓS o Prompt 1 para que as entidades sejam
# âncoras confirmadas. Tentar extrair entidades e relações em um único prompt
# aumenta erro de alucinação — tarefas separadas produzem output mais preciso.
#
# O contexto acumulado é injetado novamente para que relações com entidades
# de documentos ANTERIORES também possam ser detectadas.
# =============================================================================

PROMPT2_TEMPLATE = """\
Você é um resolvedor de relações entre entidades organizacionais.

{context_block}

---
## INSTRUÇÕES SOBRE O CONTEXTO ACUMULADO
Além das entidades extraídas neste documento, você pode (e deve) criar relações
com entidades **já existentes no contexto acumulado** se o documento as mencionar.
Use os nomes/títulos exatos do contexto para criar essas relações cross-documento.

Exemplo: se este documento menciona que uma Task depende de um Projeto que
já existia no contexto, você pode criar a relação belongs_to mesmo que o
Project não apareça na lista de entidades extraídas neste documento.

---
## Entidades extraídas neste documento
{entities_summary}

---
## Documento original
{document_text}

---
## Relações válidas
- belongs_to  : Task → Project    (task pertence a um projeto)
- assigned_to : Task → Person     (task atribuída a uma pessoa)
- threatens   : Risk → Project    (risco ameaça um projeto)
- answers     : Decision → OpenQuestion  (decisão responde uma pergunta aberta)
- member_of   : Person → Project  (pessoa é membro de um projeto)

## Instruções
1. Identifique TODAS as relações inferíveis com segurança.
2. Use nomes/títulos EXATAMENTE como aparecem nas listas (entidades deste doc ou do contexto).
3. Não invente relações — apenas inclua o que o documento permite inferir.
4. Priorize relações cross-documento quando o contexto confirmar a existência da entidade-alvo.

Responda APENAS com JSON válido, sem texto adicional, sem markdown:
{{
  "relations": [
    {{"from_type": "Task",     "from_title": "...", "relation": "belongs_to",  "to_type": "Project",      "to_title": "..."}},
    {{"from_type": "Task",     "from_title": "...", "relation": "assigned_to", "to_type": "Person",       "to_title": "..."}},
    {{"from_type": "Risk",     "from_title": "...", "relation": "threatens",   "to_type": "Project",      "to_title": "..."}},
    {{"from_type": "Decision", "from_title": "...", "relation": "answers",     "to_type": "OpenQuestion", "to_title": "..."}},
    {{"from_type": "Person",   "from_title": "...", "relation": "member_of",   "to_type": "Project",      "to_title": "..."}}
  ]
}}\
"""


# =============================================================================
# Funções de construção de prompts
# =============================================================================

def build_prompt1(document_text: str, context_block: str, doc_type_hint: str) -> str:
    return PROMPT1_TEMPLATE.format(
        context_block=context_block,
        doc_type_hint=doc_type_hint,
        document_text=document_text,
    )


def build_prompt2(document_text: str, extraction: dict, context_block: str) -> str:
    entities_summary = {
        "projects":       [p.name for p in extraction.get("projects", [])],
        "persons":        [p.name for p in extraction.get("persons", [])],
        "tasks":          [t.title for t in extraction.get("tasks", [])],
        "risks":          [r.title for r in extraction.get("risks", [])],
        "decisions":      [d.title for d in extraction.get("decisions", [])],
        "open_questions": [q.title for q in extraction.get("open_questions", [])],
    }
    return PROMPT2_TEMPLATE.format(
        context_block=context_block,
        entities_summary=json.dumps(entities_summary, ensure_ascii=False, indent=2),
        document_text=document_text,
    )
