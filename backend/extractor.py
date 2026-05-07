# backend/extractor.py
# =============================================================================
# Pipeline de extração de conhecimento organizacional.
#
# Arquitetura em 3 etapas:
#   Etapa 1 — LLM extrai entidades tipadas do documento
#   Etapa 2 — LLM resolve relações entre as entidades extraídas
#   Etapa 3 — Persistência no banco + atualização do AccumulatedContext
#
# Os templates dos prompts vivem em backend/prompt_templates.py para
# versionamento explícito e auditabilidade.
# =============================================================================

import json
import re
import logging
from dotenv import load_dotenv

import anthropic

from backend.parsers import parse_extraction_result, parse_relations_result
from backend.database import (
    persist_extraction,
    load_latest_context,
    build_context_block,
)
from backend.prompt_templates import build_prompt1, build_prompt2

load_dotenv()
logger = logging.getLogger(__name__)

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-6"


# =============================================================================
# Detecção de tipo de documento
# =============================================================================

def _detect_doc_type(text: str) -> str:
    """
    Infere se o documento é uma transcrição de reunião, thread de chat ou
    documento genérico. Resultado é injetado como hint no Prompt 1 para
    direcionar a extração.

    Heurísticas:
    - Chat: padrão [HH:MM] ou usuario.nome: mensagem
    - Reunião: palavras-chave de ata (Participantes, Duração, sprint, etc.)
    """
    text_lower = text[:1000].lower()

    chat_signals = [
        bool(re.search(r'\[\d{2}/\d{2}\s\d{2}:\d{2}\]', text)),    # [25/03 09:12]
        bool(re.search(r'\[\d{2}:\d{2}\]', text)),                   # [09:12]
        bool(re.search(r'#[\w-]+\n', text)),                          # #canal
        text_lower.count(':') > 8 and '\n' in text[:500],            # muitas linhas user: msg
    ]

    meeting_signals = [
        'participantes:' in text_lower,
        'duração:' in text_lower,
        'sprint' in text_lower and 'planning' in text_lower,
        'weekly sync' in text_lower or 'reunião' in text_lower,
        'pauta:' in text_lower or 'ata:' in text_lower,
    ]

    chat_score    = sum(bool(s) for s in chat_signals)
    meeting_score = sum(bool(s) for s in meeting_signals)

    if chat_score >= 2:
        return (
            "THREAD DE CHAT — As entidades emergem de mensagens informais ao longo do tempo. "
            "Extraia o **estado mais recente** de cada entidade, ignorando versões anteriores "
            "na mesma thread. Status updates e descobertas técnicas devem ser capturados como "
            "Tasks ou Risks conforme apropriado."
        )
    if meeting_score >= 2:
        return (
            "TRANSCRIÇÃO DE REUNIÃO — As decisões são declaradas formalmente. "
            "Capture decisões explícitas ('João decide...', 'aprovado...'), tarefas com "
            "responsável e prazo, riscos levantados, e perguntas sem resposta ao final."
        )
    return (
        "DOCUMENTO ORGANIZACIONAL — Extraia todas as entidades relevantes sem assumir "
        "estrutura específica de formato."
    )


# =============================================================================
# Helpers LLM
# =============================================================================

def _extract_json(text: str) -> str:
    """Remove markdown fences e retorna só o JSON."""
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    return match.group(1).strip() if match else text.strip()


def _call_llm(prompt: str, max_tokens: int = 4096) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


# =============================================================================
# Pipeline principal
# =============================================================================

def run_extraction(document_text: str, source_doc: str) -> dict:
    """
    Executa o pipeline completo de extração para um documento.

    Retorna:
        {
            "extraction":   dict com as listas de entidades parseadas,
            "relations":    list de relações parseadas,
            "parse_errors": int,
            "source_doc":   str,
        }
    """
    # ── Etapa 0: contexto acumulado ──────────────────────────────────────────
    ctx = load_latest_context()
    context_block = (
        build_context_block(ctx) if ctx
        else "## Contexto acumulado\nNenhum documento processado anteriormente. Esta é a primeira extração."
    )

    # Detecção de tipo de documento — injeta hint contextual no Prompt 1
    doc_type_hint = _detect_doc_type(document_text)
    logger.info(f"[extractor] Tipo detectado para '{source_doc}': {doc_type_hint[:60]}...")

    # ── Etapa 1: extração de entidades ───────────────────────────────────────
    logger.info(f"[extractor] Prompt 1 — extraindo entidades de '{source_doc}'")
    prompt1 = build_prompt1(document_text, context_block, doc_type_hint)
    raw1 = _call_llm(prompt1)

    try:
        json1 = json.loads(_extract_json(raw1))
    except json.JSONDecodeError as e:
        logger.error(f"[extractor] Prompt 1 — JSON inválido: {e}\nRaw: {raw1[:500]}")
        raise ValueError(f"Prompt 1 retornou JSON inválido: {e}") from e

    extraction = parse_extraction_result(json1, source_doc)
    logger.info(
        "[extractor] Etapa 1 concluída — "
        f"projects={len(extraction['projects'])}, persons={len(extraction['persons'])}, "
        f"tasks={len(extraction['tasks'])}, risks={len(extraction['risks'])}, "
        f"decisions={len(extraction['decisions'])}, "
        f"open_questions={len(extraction['open_questions'])}"
    )

    # ── Etapa 2: resolução de relações ───────────────────────────────────────
    logger.info("[extractor] Prompt 2 — resolvendo relações")
    prompt2 = build_prompt2(document_text, extraction, context_block)
    raw2 = _call_llm(prompt2)

    try:
        json2 = json.loads(_extract_json(raw2))
    except json.JSONDecodeError as e:
        logger.error(f"[extractor] Prompt 2 — JSON inválido: {e}\nRaw: {raw2[:500]}")
        raise ValueError(f"Prompt 2 retornou JSON inválido: {e}") from e

    relations = parse_relations_result(json2)
    logger.info(f"[extractor] Etapa 2 concluída — {len(relations)} relações")

    # ── Etapa 3: persistência + snapshot de contexto ─────────────────────────
    logger.info("[extractor] Etapa 3 — persistindo no banco")
    persist_extraction(extraction, relations, source_doc)
    logger.info("[extractor] Pipeline concluído.")

    return {
        "extraction":   extraction,
        "relations":    relations,
        "parse_errors": extraction.get("parse_errors", 0),
        "source_doc":   source_doc,
    }
