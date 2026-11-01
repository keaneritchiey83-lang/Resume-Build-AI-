"""Deterministic, auditable career workflows. No autonomous external actions."""
from __future__ import annotations
import hashlib
import re
from typing import Any

WORDS = re.compile(r"[a-z][a-z0-9+#.-]{2,}", re.I)
STOP = frozenset('the and for with from your our you are was were have has had this that will into their they them each work role job position experience skills required ability including across through using'.split())

def keywords(text: str) -> set[str]:
    return {w.lower().strip('.-') for w in WORDS.findall(text) if w.lower() not in STOP}

def evidence_match(requirements: list[str], evidence: list[dict[str, str]]) -> dict[str, Any]:
    """Conservative lexical matcher; explicitly not proof of qualifications."""
    rows = []
    for requirement in requirements:
        req = keywords(requirement)
        ranked = []
        for item in evidence:
            terms = keywords(item['description'])
            overlap = sorted(req & terms)
            score = len(overlap) / max(1, len(req))
            ranked.append((score, len(overlap), item['id'], overlap))
        ranked.sort(key=lambda x: (-x[0], -x[1], x[2]))
        top = ranked[0] if ranked else None
        rows.append({'requirement': requirement, 'matched_evidence_ids': [top[2]] if top and top[0] >= 0.5 and top[1] >= 2 else [],
                     'overlapping_terms': top[3] if top and top[0] >= 0.5 and top[1] >= 2 else [],
                     'needs_human_review': True, 'status': 'potential_match' if top and top[0] >= 0.5 and top[1] >= 2 else 'gap'})
    return {'requirements': rows, 'potential_matches': sum(r['status']=='potential_match' for r in rows),
            'total_requirements': len(rows), 'disclaimer': 'Lexical screening only. Human must verify facts and qualifications; no missing credentials may be invented.'}

def interview_plan(competencies: list[str], evidence: list[dict[str, str]]) -> dict[str, Any]:
    matched = evidence_match(competencies, evidence)
    questions = []
    for i, row in enumerate(matched['requirements'], 1):
        questions.append({'number': i, 'competency': row['requirement'],
                          'question': f"Describe a specific time you demonstrated {row['requirement']}. What was your role, what actions did you take, and what was the verified result?",
                          'suggested_evidence_ids': row['matched_evidence_ids'],
                          'rubric': ['situation', 'task', 'personal_actions', 'verified_result', 'technical_accuracy'],
                          'requires_human_fact_verification': True})
    return {'questions': questions, 'rule': 'Do not invent scenarios, numerical achievements, certifications, or results.'}

def answer_review(answer: str) -> dict[str, Any]:
    """Coaching signals, NOT an interview score or hiring prediction."""
    lower = answer.lower()
    signals = {'situation': any(t in lower for t in ['during ', 'when ', 'while ', 'at the ']),
               'task': any(t in lower for t in ['needed to', 'responsible for', 'assigned to', 'objective']),
               'personal_actions': any(t in lower for t in ['i ', 'my ', 'i\u2019', "i'"]),
               'verified_result': any(t in lower for t in ['result', 'completed', 'achieved', 'verified', 'confirmed']),
               'technical_accuracy': False}
    return {'coaching_signals': signals, 'review_required': True,
            'feedback': [f'Clarify {name.replace("_", " ")} with a specific truthful example.' for name, found in signals.items() if not found],
            'disclaimer': 'Heuristic text prompts only; technical accuracy, individual ownership, and outcomes require human review.'}

RELEASE_CHECKS = ('npm_install', 'vite_production_build', 'backend_tests', 'migration_upgrade', 'postgres_health', 'docker_compose_smoke', 'security_review', 'staging_failover')

def release_gate(attestations: list[dict[str, str]]) -> dict[str, Any]:
    """Operator-supplied evidence is never treated as independently verified."""
    by_check = {a['check']: a for a in attestations if a['check'] in RELEASE_CHECKS}
    details = []
    for check in RELEASE_CHECKS:
        item = by_check.get(check)
        accepted = bool(item and item['status'] == 'passed' and item.get('evidence_uri') and item.get('reviewer'))
        details.append({'check': check, 'reported_status': item['status'] if item else 'missing', 'evidence_recorded': accepted,
                        'verified_by_service': False})
    return {'release_unblocked': False, 'operator_evidence_complete': all(d['evidence_recorded'] for d in details),
            'checks': details, 'next_step': 'Independent CI/CD and authorized production change approval required. This API cannot authorize deployment.'}
