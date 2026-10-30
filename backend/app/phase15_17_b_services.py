"""Bounded B-track services: evidence-only drafts, practice scoring, and safe operations plans."""
from __future__ import annotations
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from typing import Any
from app.phase15_17_services import evidence_match, answer_review, RELEASE_CHECKS

TEMPLATES = {'general': 'Professional Resume', 'federal': 'Federal Resume', 'technical': 'Technical Resume'}

def resume_draft(*, candidate_name: str, target_role: str, summary: str, requirements: list[str], evidence: list[dict], template: str) -> dict[str, Any]:
    """Produces editable text/HTML (print-to-PDF); never invents experience or PII."""
    mapping = evidence_match(requirements, evidence)
    lines = [candidate_name, target_role, TEMPLATES[template], '', 'PROFESSIONAL SUMMARY', summary.strip(), '', 'VERIFIED EXPERIENCE / EVIDENCE (REVIEW BEFORE USE)']
    for item in evidence:
        lines.append(f"- {item['description'].strip()} [Source: {item['id']}]")
    lines.extend(['', 'ROLE REQUIREMENTS TO VALIDATE'])
    for match in mapping['requirements']:
        lines.append(f"- {match['requirement']} — {'Potential evidence: ' + ', '.join(match['matched_evidence_ids']) if match['matched_evidence_ids'] else 'GAP: supply authentic evidence'}")
    if template == 'federal':
        lines.extend(['', 'FEDERAL APPLICATION COMPLETENESS CHECK', 'Add verified employer names, job dates, hours/week, grade/series if applicable, duties, and quantified results before submitting.'])
    text = '\n'.join(lines)
    # HTML export uses escaping; never executes resume content as markup.
    body = '<pre style="white-space:pre-wrap;font:11pt Arial,sans-serif;line-height:1.45">' + html.escape(text) + '</pre>'
    output_html = '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Resume draft</title></head><body>' + body + '</body></html>'
    return {'template':template, 'resume_text':text, 'resume_html':output_html, 'evidence_map':mapping, 'export_formats':['text','html (browser print-to-PDF)'], 'disclaimer':'DRAFT ONLY. Human must verify every statement. No automatic application or ATS prediction.'}

RUBRIC = {'situation': 5, 'task': 5, 'personal_actions': 5, 'verified_result': 5, 'specificity': 5, 'reflection': 5}

def interview_simulation(question: str, answer: str, competency: str) -> dict[str, Any]:
    """Transparent practice-only heuristic; no assertion of factual correctness."""
    lower = answer.lower()
    coach = answer_review(answer)['coaching_signals']
    scores = {
        'situation': 4 if coach['situation'] else 0,
        'task': 4 if coach['task'] else 0,
        'personal_actions': 4 if coach['personal_actions'] else 0,
        'verified_result': 4 if coach['verified_result'] else 0,
        'specificity': 4 if bool(re.search(r'\b\d+(?:\.\d+)?\b', answer)) or any(word in lower for word in ('specifically','for example','first,','then,')) else 0,
        'reflection': 4 if any(word in lower for word in ('learned','improved','next time','afterward','recommend')) else 0,
    }
    feedback = [f'Provide a concrete {key.replace("_", " ")} statement supported by your real experience.' for key, value in scores.items() if value == 0]
    return {'question':question, 'competency':competency, 'practice_score':sum(scores.values()), 'practice_max':sum(RUBRIC.values()), 'rubric_scores':scores, 'rubric_maxima':RUBRIC, 'feedback':feedback or ['Review evidence and confirm every claimed result.'], 'follow_up_question':f'What documented evidence supports your result for {competency}?', 'fact_checked':False, 'hiring_prediction':None, 'note':'Practice-only keyword rubric, not a calibrated human interview assessment. Scores cannot verify truth, safety compliance or technical accuracy.'}

def operations_plan(regions: list[dict], attestations: list[dict], desired_primary: str | None = None) -> dict[str, Any]:
    """Read-only cross-region operations report; never triggers traffic changes or data writes."""
    ids = {r['region_id'] for r in regions}
    by_check = {a['check']: a for a in attestations}
    missing = [x for x in RELEASE_CHECKS if x not in by_check or by_check[x]['status'] != 'passed' or not by_check[x].get('evidence_uri') or not by_check[x].get('reviewer')]
    healthy = [r['region_id'] for r in regions if r['reported_health']=='healthy']
    blockers = ['Independent health, replication and RPO/RTO validation required', 'Human-approved change window and rollback procedure required']
    if len(regions) < 2: blockers.append('At least two independently deployed regions required')
    if missing: blockers.append('Missing operator-attested checks: '+', '.join(missing))
    if desired_primary and desired_primary not in ids: blockers.append('Requested primary is not in region inventory')
    if desired_primary and desired_primary not in healthy: blockers.append('Requested primary is not reported healthy')
    payload = {'regions':regions, 'desired_primary':desired_primary, 'missing_checks':missing}
    return {'plan_id':hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:20], 'mode':'read_only_dry_run', 'missing_checks':missing, 'reported_healthy_regions':healthy, 'blockers':blockers, 'requires_change_approval':True, 'requires_independent_observation':True, 'automatic_failover_enabled':False, 'deployment_executed':False, 'failover_executed':False, 'generated_at_utc':datetime.now(timezone.utc).isoformat(), 'steps':['Verify independently observed replication lag and consistency','Confirm target region readiness and DNS/traffic routing ownership','Obtain documented authorized change approval','Run staged manual cutover with rollback and smoke checks','Collect signed evidence and post-event review']}
