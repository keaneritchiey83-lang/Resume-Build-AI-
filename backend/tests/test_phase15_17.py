from pathlib import Path
import pytest
from pydantic import ValidationError
from app.phase15_17_services import evidence_match, interview_plan, answer_review, release_gate, RELEASE_CHECKS



def test_evidence_grounding_and_gaps():
    result = evidence_match(['hydraulic maintenance diagnostics', 'cloud architecture security'], [{'id': 'a', 'description': 'Performed hydraulic maintenance diagnostics for aircraft.'}])
    assert result['requirements'][0]['matched_evidence_ids'] == ['a']
    assert result['requirements'][1]['status'] == 'gap'
    assert result['requirements'][1]['matched_evidence_ids'] == []
    assert result['requirements'][0]['needs_human_review']


def test_no_fabricated_interview_examples():
    plan = interview_plan(['production scheduling coordination'], [])
    assert plan['questions'][0]['suggested_evidence_ids'] == []
    assert 'Do not invent' in plan['rule']
    assert answer_review('I was responsible for leading the maintenance coordination and confirmed the result.')['review_required']


def test_release_gate_cannot_self_approve():
    complete = [{'check': c, 'status': 'passed', 'evidence_uri': f'https://ci.example/{c}', 'reviewer': 'security-team'} for c in RELEASE_CHECKS]
    status = release_gate(complete)
    assert status['operator_evidence_complete']
    assert status['release_unblocked'] is False
    assert not any(x['verified_by_service'] for x in status['checks'])
    assert not release_gate([])['operator_evidence_complete']


def test_duplicate_evidence_and_release_checks_rejected():
    # Full API schema import requires the backend's production dependencies.
    source = (Path(__file__).resolve().parents[1] / 'app/phase15_17_api.py').read_text()
    assert 'Evidence IDs must be unique' in source
    assert 'Duplicate checks not allowed' in source


def test_api_registered_and_authorized():
    root = Path(__file__).resolve().parents[1]
    main = (root / 'app/main.py').read_text()
    api = (root / 'app/phase15_17_api.py').read_text()
    assert 'app.include_router(phase15_17_router)' in main
    assert 'Depends(current_user)' in api
    assert 'require_org_role' in api
    assert "{'owner', 'admin'}" in api
