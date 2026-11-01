"""Phases 15–17: authenticated, tenant-scoped analysis and release controls."""
from __future__ import annotations
from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import current_user
from app.db import get_session
from app.models import User
from app.tenancy import require_org_role
from app.phase15_17_services import evidence_match, interview_plan, answer_review, release_gate, RELEASE_CHECKS

router = APIRouter(prefix='/v1', tags=['phase15-17'])

class Evidence(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    description: str = Field(min_length=8, max_length=4000)

class CareerInput(BaseModel):
    organization_id: str = Field(min_length=1, max_length=36)
    requirements: list[str] = Field(min_length=1, max_length=30)
    evidence: list[Evidence] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def validate_content(self):
        if any(not 3 <= len(req.strip()) <= 500 for req in self.requirements):
            raise ValueError('Each requirement must contain 3-500 characters')
        ids = [item.id for item in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError('Evidence IDs must be unique')
        return self

class AnswerInput(BaseModel):
    organization_id: str = Field(min_length=1, max_length=36)
    answer: str = Field(min_length=20, max_length=12000)

class Attestation(BaseModel):
    check: Literal['npm_install', 'vite_production_build', 'backend_tests', 'migration_upgrade', 'postgres_health', 'docker_compose_smoke', 'security_review', 'staging_failover']
    status: Literal['passed', 'failed', 'blocked', 'pending']
    evidence_uri: str = Field(default='', max_length=2000)
    reviewer: str = Field(default='', max_length=256)

class ReleaseInput(BaseModel):
    organization_id: str = Field(min_length=1, max_length=36)
    attestations: list[Attestation] = Field(default_factory=list, max_length=8)

    @model_validator(mode='after')
    def no_duplicates(self):
        values = [i.check for i in self.attestations]
        if len(values) != len(set(values)):
            raise ValueError('Duplicate checks not allowed')
        return self

async def authorize(session: AsyncSession, user: User, org: str, roles: set[str]):
    await require_org_role(session, user, org, roles)

@router.post('/phase15/resume/evidence-map')
async def resume_evidence_map(body: CareerInput, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await authorize(session, user, body.organization_id, {'owner', 'admin', 'member'})
    return evidence_match(body.requirements, [e.model_dump() for e in body.evidence])

@router.post('/phase16/interview/plan')
async def interview_questions(body: CareerInput, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await authorize(session, user, body.organization_id, {'owner', 'admin', 'member'})
    return interview_plan(body.requirements, [e.model_dump() for e in body.evidence])

@router.post('/phase16/interview/review')
async def interview_answer_review(body: AnswerInput, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await authorize(session, user, body.organization_id, {'owner', 'admin', 'member'})
    return answer_review(body.answer)

@router.post('/phase17/release/readiness')
async def release_readiness(body: ReleaseInput, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await authorize(session, user, body.organization_id, {'owner', 'admin'})
    return release_gate([a.model_dump() for a in body.attestations])

# B-track routes reuse the same authenticated, organization-scoped service boundary.
from app.phase15_17_b_services import resume_draft, interview_simulation, operations_plan, TEMPLATES

class DraftInput(CareerInput):
    candidate_name: str = Field(min_length=2, max_length=160)
    target_role: str = Field(min_length=3, max_length=160)
    summary: str = Field(min_length=10, max_length=2000)
    template: Literal['general','federal','technical'] = 'general'

class SimulationInput(AnswerInput):
    question: str = Field(min_length=10, max_length=1000)
    competency: str = Field(min_length=3, max_length=250)

class RegionStatus(BaseModel):
    region_id: str = Field(min_length=2, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    reported_health: Literal['healthy','degraded','unavailable','unknown'] = 'unknown'

class OperationsInput(ReleaseInput):
    regions: list[RegionStatus] = Field(min_length=1, max_length=12)
    desired_primary: str | None = Field(default=None, max_length=100)

    @model_validator(mode='after')
    def unique_regions(self):
        ids = [r.region_id for r in self.regions]
        if len(ids) != len(set(ids)):
            raise ValueError('Region IDs must be unique')
        return self

@router.post('/phase15/resume/draft')
async def resume_draft_endpoint(body: DraftInput, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await authorize(session, user, body.organization_id, {'owner', 'admin', 'member'})
    return resume_draft(candidate_name=body.candidate_name, target_role=body.target_role, summary=body.summary, requirements=body.requirements, evidence=[e.model_dump() for e in body.evidence], template=body.template)

@router.post('/phase16/interview/simulate')
async def interview_simulate_endpoint(body: SimulationInput, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await authorize(session, user, body.organization_id, {'owner', 'admin', 'member'})
    return interview_simulation(question=body.question, answer=body.answer, competency=body.competency)

@router.post('/phase17/operations/plan')
async def operations_plan_endpoint(body: OperationsInput, user: User = Depends(current_user), session: AsyncSession = Depends(get_session)):
    await authorize(session, user, body.organization_id, {'owner', 'admin'})
    return operations_plan([r.model_dump() for r in body.regions], [a.model_dump() for a in body.attestations], body.desired_primary)
