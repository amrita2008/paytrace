"""Prompt builder for AI investigation.

Constructs structured prompts from reconciliation evidence.
The prompt clearly separates system instructions from transaction data.
"""

from __future__ import annotations

from backend.ai.models import InvestigationInput


_SYSTEM_INSTRUCTIONS = """You are PayTrace's investigation assistant. You examine reconciliation exceptions and produce structured, evidence-based explanations.

RULES:
1. Every factual claim MUST reference at least one evidence ID from the supplied evidence list.
2. Distinguish clearly between:
   - FACT: directly supported by supplied evidence
   - INFERENCE: reasonable interpretation supported by evidence
   - UNKNOWN: not established by available evidence
3. Prefer UNKNOWN over guessing.
4. Never invent: transaction IDs, amounts, timestamps, customer names, failure reasons, or any data not in the supplied evidence.
5. Never assume two records are related unless evidence explicitly establishes that relationship.
6. Do not reference any records or data not listed in the investigation context.

RESPONSE FORMAT — return ONLY valid JSON matching this schema:
{
  "summary": "concise one-line summary of findings",
  "observed_facts": [
    {
      "claim": "statement of fact or inference",
      "claim_type": "fact|inference|unknown",
      "evidence_ids": ["E1", "E2"]
    }
  ],
  "likely_explanation": "most plausible explanation based on evidence, or null",
  "unresolved_questions": ["question1", "question2"],
  "recommended_next_action": "specific recommended action for human review",
  "confidence": 0.0,
  "requires_human_review": true
}

CONFIDENCE RULES:
- 0.0-0.3: very uncertain, most claims are UNKNOWN
- 0.3-0.6: some evidence supports conclusions
- 0.6-0.8: strong evidence supports main conclusions
- 0.8-1.0: evidence is compelling and unambiguous
"""


def build_investigation_prompt(inp: InvestigationInput) -> str:
    """Build a structured investigation prompt from the input.

    The prompt separates system instructions from transaction data
    to resist prompt injection via transaction fields.
    """
    evidence_block = _format_evidence(inp.evidence)
    metadata_block = _format_metadata(inp.relevant_record_metadata)

    return f"""{_SYSTEM_INSTRUCTIONS}

=== INVESTIGATION CONTEXT ===

Group ID: {inp.group_id}
Exception Type: {inp.exception_type}
Payment IDs: {', '.join(inp.payment_ids) or 'none'}
Settlement IDs: {', '.join(inp.settlement_ids) or 'none'}
Bank Entry IDs: {', '.join(inp.bank_entry_ids) or 'none'}
Evidence Summary: {inp.evidence_summary or 'none available'}

=== EVIDENCE ===
{evidence_block}

=== RECORD METADATA ===
{metadata_block}

Analyze this reconciliation exception. Return ONLY valid JSON."""


def _format_evidence(evidence: list) -> str:
    """Format evidence list for the prompt."""
    if not evidence:
        return "No evidence available."
    lines = []
    for ev in evidence:
        lines.append(
            f"  [{ev.signal_id}] type={ev.signal_type} "
            f"record={ev.source_record_id} "
            f"observed=\"{ev.observed_value}\""
        )
    return "\n".join(lines)


def _format_metadata(metadata: list) -> str:
    """Format record metadata for the prompt."""
    if not metadata:
        return "No record metadata available."
    lines = []
    for m in metadata:
        parts = [f"  {m.record_id} ({m.record_type})"]
        if m.amount_paise is not None:
            parts.append(f"amount={m.amount_paise}")
        if m.currency:
            parts.append(f"currency={m.currency}")
        if m.timestamp:
            parts.append(f"time={m.timestamp}")
        if m.status:
            parts.append(f"status={m.status}")
        if m.order_id:
            parts.append(f"order={m.order_id}")
        if m.payment_refs:
            parts.append(f"refs={','.join(m.payment_refs)}")
        lines.append(" ".join(parts))
    return "\n".join(lines)
