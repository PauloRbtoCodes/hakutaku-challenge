# Prompt 1 — Extração de Entidades

**Arquivo de referência:** `backend/prompt_templates.py` → `PROMPT1_TEMPLATE`  
**Modelo:** `claude-sonnet-4-6`  
**Etapa no pipeline:** 1 de 3

---

## Responsabilidade

Dado um documento em texto livre (reunião, chat, doc), identificar e estruturar
todas as entidades organizacionais relevantes nos 6 tipos da ontologia.

---

## Variáveis injetadas

| Variável | Origem | Propósito |
|----------|--------|-----------|
| `{context_block}` | `database.build_context_block()` | Estado atual do banco (JSON) |
| `{doc_type_hint}` | `extractor._detect_doc_type()` | Dica sobre o formato do input |
| `{document_text}` | Input do usuário | O documento a ser processado |

---

## Decisões de design

### Por que injetar o contexto acumulado?

O sistema deve aprender com o tempo. Sem contexto, o LLM não sabe que "Marina"
mencionada no documento 3 é a mesma "Marina Costa" do documento 1. Com o contexto
injetado e instruções explícitas de deduplicação, o sistema consolida entidades
ao longo de múltiplos documentos.

### Por que instruções explícitas de USO do contexto?

Injetar o contexto sem instruções de uso produz resultado inconsistente — o LLM
pode ignorá-lo ou usá-lo de forma imprevisível. As 5 instruções explícitas
(deduplicação, evolução de status, resolução de ambiguidades, perguntas respondidas,
roles de pessoas) garantem comportamento determinístico.

### Por que detecção de tipo de documento?

Meeting transcripts e chat threads têm padrões semânticos diferentes:
- Reuniões: decisões explícitas ("João decide..."), tarefas formalmente atribuídas
- Chats: estado emergente ao longo de mensagens, múltiplas versões da mesma informação

O hint direciona o LLM a tratar cada formato corretamente sem alterar o schema de output.

---

## Template (simplificado)

```
Você é um extrator de entidades organizacionais...

{context_block}

INSTRUÇÕES SOBRE O CONTEXTO: [deduplicação, evolução, ambiguidades...]

TIPO DE DOCUMENTO: {doc_type_hint}

Documento: {document_text}

Responda APENAS com JSON:
{
  "projects": [...],
  "persons": [...],
  "tasks": [...],
  "risks": [...],
  "decisions": [...],
  "open_questions": [...]
}
```

Ver template completo em `backend/prompt_templates.py`.

---

## Output esperado

JSON com as 6 listas de entidades. Processado por `backend/parsers.parse_extraction_result()`.

Exemplos de saída para a Reunião 1 dos dados de teste:

```json
{
  "projects": [
    {"name": "Integração CRM", "status": "active", "description": "Integração com Salesforce/TechNova"}
  ],
  "persons": [
    {"name": "João Silva", "role": "Líder técnico", "status": "active", "aliases": []},
    {"name": "Marina Costa", "role": "Engenheira backend (Salesforce)", "status": "active", "aliases": []},
    {"name": "Pedro Almeida", "role": "Engenheiro", "status": "active", "aliases": []},
    {"name": "Ana Ferreira", "role": "Engenheira", "status": "active", "aliases": []}
  ],
  "tasks": [
    {"title": "Schema de mapeamento CRM", "status": "open", "deadline": "2025-03-28", "priority": "high", "project_name": "Integração CRM", "assignee_names": ["Marina Costa"]},
    {"title": "Configurar ambiente de staging", "status": "open", "deadline": "2025-03-31", "priority": "normal", "project_name": "Integração CRM", "assignee_names": []},
    {"title": "Documentar endpoints API TechNova", "status": "open", "deadline": "2025-04-02", "priority": "normal", "project_name": "Integração CRM", "assignee_names": ["Pedro Almeida"]}
  ],
  "risks": [
    {"title": "Cancelamento contrato TechNova se integração não entregue até abril", "status": "open", "severity": 8, "project_name": "Integração CRM"},
    {"title": "Marina como single point of failure no conhecimento Salesforce", "status": "open", "severity": 7, "project_name": "Integração CRM"}
  ],
  "decisions": [
    {"title": "Iniciar integração pelo módulo de sincronização de contatos", "status": "approved", "decided_by": "João Silva", "answers_question_title": null},
    {"title": "Marina alocada exclusivamente no backend da integração por 2 semanas", "status": "approved", "decided_by": "João Silva", "answers_question_title": null}
  ],
  "open_questions": [
    {"title": "REST API ou GraphQL para a integração?", "status": "open", "asked_by": "Marina Costa"},
    {"title": "Rate limiting: próprio ou do CRM?", "status": "open", "asked_by": "Marina Costa"}
  ]
}
```
