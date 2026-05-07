# Hakutaku AI — Organizational Intelligence Layer

Sistema de inteligência organizacional que extrai conhecimento de reuniões e chats,
constrói um grafo ontológico de entidades e relações, e gera proposals acionáveis
automaticamente. Fica mais inteligente a cada documento processado.

---

## Como rodar

### Pré-requisitos

- Python 3.11+
- Node.js 18+
- Chave de API Anthropic

### Backend

```bash
# 1. Criar e ativar venv
python -m venv venv
source venv/bin/activate          # Linux/Mac
venv\Scripts\Activate.ps1        # Windows PowerShell

# 2. Instalar dependências
pip install fastapi uvicorn sqlmodel anthropic python-dotenv

# 3. Configurar variável de ambiente
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# 4. Rodar a partir da RAIZ do projeto (não de dentro de backend/)
uvicorn backend.main:app --reload
# API em http://localhost:8000 · Docs: http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Interface em http://localhost:5173
```

### Testando com os dados de teste

Na interface, clique em **"+ Processar Doc"** e processe os 3 documentos nesta ordem:

1. **Reunião 1** — Sprint Planning 24/03 → `source_doc: reuniao-sprint-planning-24-03`
2. **Thread de Chat** — Canal #proj-crm-integration → `source_doc: chat-crm-25-29-03`
3. **Reunião 2** — Weekly Sync 28/03 → `source_doc: reuniao-weekly-sync-28-03`

A ordem importa: o sistema injeta contexto acumulado em cada extração subsequente,
demonstrando o aprendizado incremental.

### Testes

```bash
# A partir da raiz do projeto
python backend/test_database.py
python backend/test_extractor.py
python backend/test_proposals.py
```

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│  React + Vite + Tailwind + @xyflow/react                    │
│  Grafo interativo · Proposals · Modal de extração           │
└─────────────────────┬───────────────────────────────────────┘
                      │ HTTP (CORS *)
┌─────────────────────▼───────────────────────────────────────┐
│                    FASTAPI (backend/main.py)                  │
│  POST /extract · GET /graph · GET /proposals · GET /context  │
└──────┬──────────────┬───────────────────────┬───────────────┘
       │              │                       │
┌──────▼──────┐ ┌─────▼──────┐ ┌─────────────▼──────────────┐
│  extractor  │ │  database  │ │         proposals           │
│  (LLM 2x)  │ │  (SQLite)  │ │  (determinístico, 0 LLM)    │
└──────┬──────┘ └─────┬──────┘ └────────────────────────────┘
       │              │
┌──────▼──────┐ ┌─────▼──────────────────────────────────────┐
│   Anthropic │ │  AccumulatedContext (snapshot JSON do banco) │
│   Claude    │ │  injetado nos prompts de cada novo documento │
└─────────────┘ └────────────────────────────────────────────┘
```

### Fluxo de extração

```
Documento (texto livre)
       │
       ▼
[Etapa 0] Carrega AccumulatedContext + detecta tipo (reunião/chat)
       │
       ▼
[Etapa 1] Prompt 1 → Claude extrai 6 tipos de entidade (JSON)
       │
       ▼
[Etapa 2] Prompt 2 → Claude resolve relações entre entidades (JSON)
       │
       ▼
[Etapa 3] Persiste no SQLite + salva novo snapshot de AccumulatedContext
```

---

## Documento de Decisões Técnicas

### 1. Ontologia — Por que 6 tipos de entidade?

A escolha emergiu de observar como organizações **falham em converter conhecimento em ação**.

Toda operação pode ser modelada em 4 dimensões fundamentais:

| Dimensão | Entidade | Pergunta que responde |
|----------|----------|-----------------------|
| O que está sendo construído | `Project` | Quais são as unidades de valor? |
| Quem está construindo | `Person` | Quem são os agentes? |
| O trabalho concreto | `Task` | O que precisa ser feito? |
| O que pode dar errado | `Risk` | Quais são as ameaças? |

E 2 entidades para modelar o **ciclo cognitivo das decisões**:

| Dimensão | Entidade | Pergunta que responde |
|----------|----------|-----------------------|
| O que foi decidido | `Decision` | O que já está resolvido? |
| O que ainda não se sabe | `OpenQuestion` | O que está bloqueando? |

A distinção entre `Decision` e `OpenQuestion` é central: organizações saudáveis convertem
OpenQuestions em Decisions sistematicamente. O sistema monitora essa conversão e gera
proposals quando perguntas ficam abertas por tempo demais ou quando uma Decision já
responde uma OpenQuestion mas ela ainda aparece como `open`.

**Trade-off consciente:** 6 tipos fixos vs. schema extensível. Tipos fixos produzem extração
LLM mais confiável e prompts menores. Um schema dinâmico exigiria prompt gerado em runtime
e parsing genérico — mais flexível, muito menos previsível. Para um MVP: precisão > flexibilidade.

---

### 2. Estados das entidades — Por que esses e não outros?

Cada estado captura **transições com valor operacional real**:

#### Task
| Estado | Por que existe |
|--------|----------------|
| `orphan` | Estado **computado** (sem assignee). Revela falha de atribuição que nenhuma ata registra explicitamente. Uma task sem dono é uma task que não será feita. |
| `overdue` | Distinção de `open` — prazo passou. Permite proposals específicos de revisão de deadline. |
| `in_progress` | Sinaliza trabalho ativo. Um projeto com todas as tasks `open` pode estar parado; com `in_progress`, está se movendo. |

#### Risk
| Estado/Campo | Por que existe |
|--------------|----------------|
| Severity **monotônica** | Organizações raramente percebem menos risco sem mitigação formal. A severity só cresce automaticamente — reduzir exige decisão explícita (`mitigated` ou `dismissed`). |
| `critical` vs `open` | Um risco `open` de severity 9 requer tratamento diferente de um `open` de severity 3. O estado `critical` captura urgência além da severidade numérica. |
| `dismissed` | Encerramento explícito sem mitigação — distinção importante de `mitigated`. |

#### Decision
| Estado | Por que existe |
|--------|----------------|
| `reversed` | Captura mudanças de posição ao longo do tempo. A reunião 1 decide X; a reunião 3 reverte. Sem esse estado, o histórico decisório seria perdido. |
| `proposed` | Permite decisões em discussão antes da aprovação formal. |

---

### 3. Relações — Por que essas 5?

As 5 relações cobrem os padrões operacionais mais relevantes para geração de proposals:

| Relação | Valor operacional |
|---------|-------------------|
| `belongs_to` (Task→Project) | Filtra tasks por projeto; detecta projetos sem tasks |
| `assigned_to` (Task→Person) | Detecta sobrecarga de pessoas; tasks sem dono (orphan) |
| `threatens` (Risk→Project) | Escopa riscos; calcula exposição total de um projeto |
| `answers` (Decision→OpenQuestion) | Detecta quando perguntas foram respondidas implicitamente |
| `member_of` (Person→Project) | Detecta SPOF (projeto com apenas 1 pessoa) |

**Relação considerada mas não implementada:** `depends_on` (Task→Task). Modelar dependências
entre tasks seria valioso mas exigiria um 3º prompt LLM para resolução de dependências,
aumentando latência e custo. Decidido para v2.

---

### 4. Pipeline de extração — Por que 2 prompts?

**Um único prompt para entidades + relações** teria 2 problemas:

1. **Output muito longo**: aumenta risco de truncamento e erros de parsing
2. **Relações dependem de entidades confirmadas como âncoras**: o LLM pode criar relações
   para entidades que ele mesmo inventou no mesmo prompt. Com 2 etapas, o Prompt 2 só vê
   entidades parseadas e validadas — sem alucinação cruzada.

**Por que não 3+ prompts?** Cada chamada LLM adiciona 2-5s de latência e custo.
2 prompts é o ponto de equilíbrio entre precisão e performance para este sistema.

#### Detecção automática de tipo de documento

O sistema detecta automaticamente se o input é uma **reunião** (heurísticas: "Participantes:",
"Duração:", "sprint planning") ou **thread de chat** (heurísticas: padrão `[HH:MM]`, `#canal`,
alta densidade de `:`). O tipo detectado é injetado como *hint* no Prompt 1:

- **Reuniões**: o LLM foca em decisões formais explícitas e tasks com responsável definido
- **Chats**: o LLM foca no **estado mais recente** de cada entidade, ignorando versões intermediárias

---

### 5. O sistema aprende — AccumulatedContext

**Este é o mecanismo central de aprendizado incremental.**

Após cada documento, um snapshot JSON completo do banco é salvo na tabela `accumulated_context`
e injetado nos prompts do próximo documento com instruções explícitas de uso:

```json
{
  "document_count": 2,
  "last_source_doc": "reuniao-sprint-24-03",
  "projects": [{"id": 1, "name": "Integração CRM", "status": "active"}],
  "persons": [{"id": 1, "name": "Marina Costa", "role": "Engenheira backend (Salesforce)"}],
  "tasks": [...], "risks": [...], "decisions": [...], "open_questions": [...]
}
```

As instruções explícitas no prompt garantem:

1. **Deduplicação semântica**: "Marina" no doc 3 = "Marina Costa" do contexto → mesma entidade
2. **Evolução de status**: risco de TechNova era severity 7; se doc menciona situação crítica → severity 9 + status "critical"
3. **Resolução de ambiguidades**: "o projeto" → contexto tem 1 projeto ativo → inferência correta
4. **Cross-doc linking**: Decision "Usar REST API" (doc 2) responde OpenQuestion "REST vs GraphQL" (doc 1) → relação `answers` cross-documento

**Na prática com os dados de teste:**

- Doc 1 (Reunião 1): extrai risco TechNova com severity 8, pergunta "REST vs GraphQL" como open
- Doc 2 (Chat): contexto injeta que risco TechNova existe → escalada para severity 9, "critical"
- Doc 3 (Reunião 2): contexto injeta a pergunta "REST vs GraphQL" → Decision "Usar REST API" linkada como `answers`

**Trade-off principal:** snapshot completo cresce linearmente com o banco. Para organizações
grandes, seria necessário summarização do contexto (manter apenas entidades ativas + últimas N
modificadas). Limitação de escala conhecida e documentada.

---

### 6. Proposals determinísticos — Por que sem LLM?

| Regra | Gatilho | Valor |
|-------|---------|-------|
| `orphan_task` | Task sem assignee | Tasks sem dono nunca são feitas |
| `overdue_task` | Task com prazo vencido | Atraso detectado automaticamente |
| `critical_risk` | Risk severity ≥ 7 | Risco alto sem plano de mitigação |
| `answered_question` | Decision responde OpenQuestion ainda open | Fechamento de loop |
| `spof` | Projeto ativo com exatamente 1 pessoa | Single point of failure |
| `stale_question` | OpenQuestion open desde doc anterior | Perguntas esquecidas |

**Por que determinístico e não LLM?**
- **0 latência**: proposals instantâneos, sem esperar API
- **0 custo**: sem chamadas LLM em leituras
- **Auditável**: um gestor entende exatamente por que cada proposal foi gerado
- **Reproduzível**: mesmo estado do banco → mesmo conjunto de proposals

LLM seria mais poderoso para detectar padrões sutis (ex: "Pedro sempre atrasa tasks de
documentação"), mas o custo-benefício para MVP não justifica. A arquitetura permite adicionar
`GET /proposals/llm` para análise mais profunda sem mudar a estrutura existente.

---

### 7. Schema de banco — Decisões de persistência

**Chave de unicidade: nome/título, não ID**

Entities são deduplicadas por `name` (Project, Person) ou `title` (Task, Risk, Decision,
OpenQuestion). Humanos se referem a entidades pelos nomes — usar IDs exigiria lookup por nome
que seria equivalente, com mais complexidade.

**Trade-off:** "João" pode ser duas pessoas em empresas maiores. Solução parcial: campo
`aliases` no modelo Person permite consolidar variações de nome.

**Estratégia de upsert: INSERT / UPDATE_STATE / ENRICH**

- `UPDATE_STATE`: status ou severity diverge → atualiza (never reduz severity de Risk)
- `ENRICH`: campos opcionais nulos recebem novo valor → preenche
- `INSERT`: entidade nova → cria

**Many-to-many via tabelas de link explícitas**

`TaskPersonLink` e `PersonProjectLink` em vez de campos JSON. Permite queries SQL diretas
para SPOF detection e orphan detection sem deserialização.

---

### 8. Resumo de trade-offs

| Decisão | Escolha | Alternativa | Razão |
|---------|---------|-------------|-------|
| Banco | SQLite | PostgreSQL | Zero config, portabilidade, suficiente para MVP |
| LLM | Claude Sonnet 4.6 | GPT-4o | Melhor instruction-following para JSON estruturado |
| Prompts | 2 separados | 1 único / 3+ | Equilíbrio precisão × latência |
| Proposals | Determinístico | LLM | 0 latência, 0 custo, auditável |
| Contexto | Snapshot completo | Incremental | Simplicidade; limitação de escala conhecida |
| Frontend | React Flow | D3 | API alto nível para grafos, sem overhead de SVG manual |
| Deduplicação | Por nome/título | Por ID | Alinhado com como humanos referenciam entidades |

---

## Estrutura do repositório

```
hakutaku-challenge/
├── backend/
│   ├── main.py              # FastAPI — 5 endpoints
│   ├── models.py            # Ontologia SQLModel (6 entidades + enums)
│   ├── database.py          # Persistência, upserts, AccumulatedContext
│   ├── extractor.py         # Pipeline 3 etapas + detecção de tipo de doc
│   ├── prompt_templates.py  # Templates dos 2 prompts LLM (versionados)
│   ├── parsers.py           # Parsing defensivo do output LLM
│   ├── proposals.py         # 6 regras determinísticas
│   └── test_*.py            # Testes de fumaça
├── prompts/
│   ├── 01_entity_extraction.md    # Prompt 1 documentado + rationale + exemplos
│   └── 02_relation_resolution.md  # Prompt 2 documentado + rationale
├── frontend/
│   ├── src/pages/MainPage.jsx     # Layout principal
│   ├── src/components/            # EntityNode, ProposalCard, ExtractModal, etc.
│   ├── src/hooks/                 # useGraph, useProposals, useOrgContext
│   └── src/api/client.js          # Chamadas HTTP centralizadas
└── README.md                      # Este arquivo
```

---

## API Reference

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/health` | Healthcheck |
| `POST` | `/extract` | Processa documento; retorna contagens |
| `GET` | `/graph` | Retorna `{nodes, edges}` para React Flow |
| `GET` | `/proposals` | Retorna proposals determinísticos |
| `GET` | `/context` | Retorna snapshot mais recente do AccumulatedContext |

**POST /extract**

```json
// Request
{ "document_text": "Participantes: João...", "source_doc": "reuniao-sprint-24-03" }

// Response
{
  "source_doc": "reuniao-sprint-24-03",
  "parse_errors": 0,
  "counts": { "projects": 1, "persons": 4, "tasks": 3, "risks": 2, "decisions": 2, "open_questions": 2, "relations": 8 }
}
```
