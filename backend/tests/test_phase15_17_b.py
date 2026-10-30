from pathlib import Path
from app.phase15_17_b_services import resume_draft, interview_simulation, operations_plan


def test_resume_draft_escapes_html_and_does_not_invent():
    result = resume_draft(candidate_name='Test Candidate', target_role='Engineer', summary='Experienced professional with documented work.', requirements=['cloud architecture skills'], evidence=[{'id':'e1','description':'Performed scheduled aircraft inspections.'}], template='federal')
    assert 'GAP: supply authentic evidence' in result['resume_text']
    assert 'FEDERAL APPLICATION COMPLETENESS CHECK' in result['resume_text']
    assert result['evidence_map']['potential_matches'] == 0
    script = resume_draft(candidate_name='<script>alert(1)</script>',target_role='Engineer',summary='Verified engineering experience',requirements=['engineering design'],evidence=[],template='general')
    assert '<script>' not in script['resume_html']


def test_simulation_is_conservative():
    review = interview_simulation('What did you do during a conflict?', 'I was responsible for the issue and verified the result.', 'leadership')
    assert review['practice_score'] < 30
    assert review['fact_checked'] is False
    assert review['hiring_prediction'] is None


def test_operations_never_changes_regions():
    report = operations_plan([{'region_id':'east','reported_health':'healthy'},{'region_id':'west','reported_health':'degraded'}],[], 'west')
    assert report['automatic_failover_enabled'] is False
    assert report['failover_executed'] is False
    assert report['missing_checks']
    assert any('not reported healthy' in issue for issue in report['blockers'])


def test_routes_and_dashboard_present():
    root = Path(__file__).resolve().parents[2]
    api = (root / 'backend/app/phase15_17_api.py').read_text()
    ui = (root / 'frontend/src/App.tsx').read_text()
    for route in ['/phase15/resume/draft', '/phase16/interview/simulate', '/phase17/operations/plan']:
        assert route in api
    assert 'Phase1517StudioPanel' in ui
