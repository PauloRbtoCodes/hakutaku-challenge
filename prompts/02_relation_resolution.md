# Prompt 2 — Resolução de Relações

**Arquivo de referência:** `backend/prompt_templates.py` → `PROMPT2_TEMPLATE`  
**Modelo:** `claude-sonnet-4-6`  
**Etapa no pipeline:** 2 de 3

---

## Responsabilidade

Dado o conjunto de entidades extraídas pelo Prompt 1 e o documento original,
identificar todas as relações válidas entre as entidades — incluindo relações
com entidades de documentos anteriores presentes no contexto.

---

## Variáveis injetadas

| Variável | Origem | Propósito |
|----------|--------|-----------|
| `{context_block}` | `database.build_context_block()` | Estado atual do banco |
| `{entities_summary}` | Saída do Prompt 1 | Entidades confirmadas deste doc |
| `{document_text}` | Input do usuário | Documento original para inferência |

---

## Decisões de design

### Por que executar APÓS o Prompt 1?

Resolver relações exige entidades confirmadas como âncoras. Tentar extrair
entidades e relações em um único prompt aumenta o risco de alucinação — o LLM
pode criar relações para entidades que ele mesmo inventou. A separação em 2
prompts garante que as relações referenciem apenas entidades que existem.

### Por que injetar o contexto no Prompt 2 também?

Para habilitar relações **cross-documento**: uma Task deste documento pode
pertencer a um Project que existia em documentos anteriores e não foi
re-extraído neste. Sem o contexto, essa relação seria perdida.

### Relações suportadas

| Relação | De | Para | Semântica |
|---------|-----|------|-----------|
| `belongs_to` | Task | Project | Task pertence a um projeto |
| `assigned_to` | Task | Person | Task atribuída a uma pessoa |
| `threatens` | Risk | Project | Risco ameaça um projeto |
| `answers` | Decision | OpenQuestion | Decisão responde uma pergunta |
| `member_of` | Person | Project | Pessoa é membro de um projeto |

---

## Exemplos de relações cross-documento

Reunião 1 → extrai OpenQuestion "REST API ou GraphQL?"
Reunião 2 → extrai Decision "Usar REST API"

O Prompt 2 da Reunião 2, com o contexto acumulado, deve produzir:
```json
{
  "from_type": "Decision",
  "from_title": "Usar REST API para integração",
  "relation": "answers",
  "to_type": "OpenQuestion",
  "to_title": "REST API ou GraphQL para a integração?"
}
```

Esta relação `answers` conecta as duas entidades e o sistema de proposals
pode então sugerir marcar a pergunta como "answered".

---

## Output esperado

JSON com lista de relações. Processado por `backend/parsers.parse_relations_result()`.

```json
{
  "relations": [
    {"from_type": "Task", "from_title": "Schema de mapeamento CRM", "relation": "belongs_to", "to_type": "Project", "to_title": "Integração CRM"},
    {"from_type": "Task", "from_title": "Schema de mapeamento CRM", "relation": "assigned_to", "to_type": "Person", "to_title": "Marina Costa"},
    {"from_type": "Risk", "from_title": "Cancelamento contrato TechNova", "relation": "threatens", "to_type": "Project", "to_title": "Integração CRM"},
    {"from_type": "Marina Costa", "from_title": "Marina Costa", "relation": "member_of", "to_type": "Project", "to_title": "Integração CRM"}
  ]
}
```
