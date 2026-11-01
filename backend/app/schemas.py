from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)
    mfa_code: str = Field(default="", max_length=12)


class UserResponse(BaseModel):
    id: str
    email: str
    is_platform_admin: bool
    mfa_enabled: bool


class MFAConfirmRequest(BaseModel):
    code: str = Field(min_length=6, max_length=12)


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=300)
    slug: str = Field(min_length=2, max_length=300)


class MembershipInvite(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: Literal["admin", "recruiter", "member"] = "member"


class ProviderCredentialRequest(BaseModel):
    credentials: dict[str, Any]
    enabled: bool = True


class PartnerJobRequest(BaseModel):
    external_job_id: str = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(min_length=30, max_length=65_000)
    location: str = Field(default="", max_length=500)
    country: str = Field(default="US", min_length=2, max_length=2)
    city_region_postal: str = Field(default="", max_length=500)
    employer_name: str = Field(min_length=1, max_length=500)
    company_website: str = Field(default="", max_length=2000)
    public_job_url: str = Field(default="", max_length=2000)
    apply_url: str = Field(default="", max_length=2000)
    poster_email: str = Field(default="", max_length=320)
    job_type: str = Field(default="full_time", max_length=100)
    date_published: datetime | None = None
    operation: Literal["CREATE", "UPDATE", "CLOSE", "RENEW"] = "CREATE"
    provider_job_id: str = Field(default="", max_length=1000)


class Experience(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    organization: str = Field(min_length=1, max_length=300)
    location: str = Field(default="", max_length=300)
    start_date: str = Field(default="", max_length=100)
    end_date: str = Field(default="", max_length=100)
    bullets: list[str] = Field(default_factory=list)


class Education(BaseModel):
    credential: str = Field(min_length=1, max_length=500)
    institution: str = Field(min_length=1, max_length=500)
    graduation_date: str = Field(default="", max_length=100)


class CandidateProfile(BaseModel):
    full_name: str = Field(min_length=1, max_length=300)
    email: str = Field(default="", max_length=320)
    phone: str = Field(default="", max_length=100)
    location: str = Field(default="", max_length=300)
    summary: str = Field(default="", max_length=5000)
    skills: list[str] = Field(default_factory=list)
    abilities: list[str] = Field(default_factory=list)
    core_values: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    publications: list[str] = Field(default_factory=list)


class TargetJob(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    organization: str = Field(default="", max_length=500)
    description: str = Field(min_length=1, max_length=100_000)
    required_skills: list[str] = Field(default_factory=list)


ResumeStyle = Literal[
    "ats",
    "hybrid",
    "federal",
    "academic_cv",
    "apa_informed_academic",
]


class AITailorRequest(BaseModel):
    target: TargetJob
    style: ResumeStyle = "ats"


class EvidenceBullet(BaseModel):
    text: str
    evidence_ids: list[str]


class ExperienceRewrite(BaseModel):
    title: str
    organization: str
    bullets: list[EvidenceBullet]


class ResumeLLMResult(BaseModel):
    headline: str
    summary: str
    skills: list[str]
    experience: list[ExperienceRewrite]
    warnings: list[str]


class TailoredResumeResponse(BaseModel):
    resume: ResumeLLMResult
    fact_count: int
    guardrails_passed: bool


class CoverLetterLLMResult(BaseModel):
    letter: str
    evidence_ids: list[str]
    warnings: list[str]


class CoverLetterResponse(BaseModel):
    cover_letter: CoverLetterLLMResult
    guardrails_passed: bool


class InterviewPlanItem(BaseModel):
    category: str
    question: str
    why_it_may_be_asked: str
    evidence_ids_to_consider: list[str]
    star_outline: list[str]


class InterviewPlan(BaseModel):
    questions: list[InterviewPlanItem]
    general_advice: list[str]


class InterviewAnswerRequest(BaseModel):
    question: str = Field(min_length=3, max_length=3000)
    answer: str = Field(min_length=3, max_length=20_000)
    target: TargetJob


class InterviewAnswerEvaluation(BaseModel):
    score: int = Field(ge=1, le=10)
    strengths: list[str]
    improvements: list[str]
    improved_star_outline: list[str]
    unsupported_claim_warning: bool


class ApplicationCreate(BaseModel):
    job_id: str | None = None
    title: str = Field(min_length=1, max_length=500)
    organization: str = Field(min_length=1, max_length=500)
    status: Literal[
        "saved",
        "applied",
        "screen",
        "interview",
        "offer",
        "rejected",
        "withdrawn",
    ] = "saved"
    notes: str = Field(default="", max_length=20_000)
    applied_at: datetime | None = None


class ApplicationResponse(BaseModel):
    id: str
    job_id: str | None
    title: str
    organization: str
    status: str
    notes: str
    applied_at: datetime | None
    created_at: datetime


class KnowledgeStageRequest(BaseModel):
    source: str = Field(min_length=2, max_length=300)
    title: str = Field(min_length=2, max_length=1000)
    content: str = Field(min_length=50, max_length=250_000)
    source_url: HttpUrl | None = None
    license: str = Field(min_length=2, max_length=500)


class USAJobsSyncRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=300)
    location: str = Field(default="", max_length=300)
    limit: int = Field(default=100, ge=1, le=500)


class ProviderResult(BaseModel):
    provider: str
    status: str
    provider_job_id: str = ""
    response: dict[str, Any]


class WebhookEventResponse(BaseModel):
    id: str
    provider: str
    event_id: str
    event_type: str
    status: str
    attempts: int
    received_at: datetime
    processed_at: datetime | None
    last_error: str


class InboundCandidateResponse(BaseModel):
    id: str
    provider: str
    provider_candidate_id: str
    full_name: str
    email: str
    phone: str
    source: str
    received_at: datetime
    retention_until: datetime


class InboundApplicationResponse(BaseModel):
    id: str
    provider: str
    provider_application_id: str
    external_job_id: str
    candidate_id: str
    source_attribution: str
    status: str
    received_at: datetime


class MonitorPolicyRequest(BaseModel):
    """Explicit candidate consent and preferences for automated monitoring."""

    enabled: bool
    acknowledged: bool = False
    purposes: list[
        Literal[
            "job_monitoring",
            "ai_career_analysis",
            "in_app_notifications",
        ]
    ] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list, max_length=30)
    target_locations: list[str] = Field(default_factory=list, max_length=30)
    remote_preference: Literal["any", "remote", "hybrid", "on_site"] = "any"
    minimum_match_score: float = Field(default=65.0, ge=0, le=100)
    cadence: Literal["realtime", "daily", "weekly"] = "daily"
    max_alerts_per_scan: int = Field(default=20, ge=1, le=100)


class MonitorPolicyResponse(BaseModel):
    enabled: bool
    purposes: list[str]
    target_roles: list[str]
    target_locations: list[str]
    remote_preference: str
    minimum_match_score: float
    cadence: str
    max_alerts_per_scan: int
    consent_version: str
    consented_at: datetime | None
    revoked_at: datetime | None
    last_scanned_at: datetime | None


class JobRecommendationResponse(BaseModel):
    id: str
    job_id: str
    title: str
    organization: str
    location: str
    apply_url: str
    score: float
    state: str
    matched_skills: list[str]
    reasons: list[str]
    evaluated_at: datetime
    notified_at: datetime | None
    agent_analyzed_at: datetime | None


class RecommendationStateUpdate(BaseModel):
    state: Literal["new", "viewed", "saved", "dismissed", "applied"]


class CareerAgentRunRequest(BaseModel):
    recommendation_id: str


class AgentEvidenceStrength(BaseModel):
    statement: str
    evidence_ids: list[str]


class FitAgentOutput(BaseModel):
    assessment: str
    strengths: list[AgentEvidenceStrength]
    gaps: list[str]
    warnings: list[str]


class ResumeStrategyOutput(BaseModel):
    headline_direction: str
    summary_focus: list[str]
    experience_focus: list[AgentEvidenceStrength]
    skills_to_emphasize: list[str]
    warnings: list[str]


class InterviewCoachOutput(BaseModel):
    questions: list[str]
    evidence_ids_to_practice: list[str]
    preparation_actions: list[str]
    warnings: list[str]


class CareerAgentReport(BaseModel):
    job_id: str
    job_title: str
    organization: str
    fit: FitAgentOutput
    resume_strategy: ResumeStrategyOutput
    interview_coaching: InterviewCoachOutput
    bounded_actions: list[str]
    prohibited_actions: list[str]


class CareerAgentRunResponse(BaseModel):
    run_id: str
    status: str
    total_tokens: int
    report: CareerAgentReport


class RecruiterStageUpdate(BaseModel):
    status: Literal[
        "received",
        "review",
        "screen",
        "interview",
        "offer",
        "hired",
        "rejected",
        "withdrawn",
    ]


class RecruiterCandidateRow(BaseModel):
    application_id: str
    candidate_id: str
    full_name: str
    email: str
    provider: str
    external_job_id: str
    source_attribution: str
    status: str
    received_at: datetime
    processing_basis: str
    privacy_notice_version: str


class RecruiterDashboardResponse(BaseModel):
    organization_id: str
    candidates: int
    applications: int
    applications_last_30_days: int
    by_stage: dict[str, int]
    by_source: dict[str, int]
    webhook_dead_letters: int


class AnalyticsPoint(BaseModel):
    day: str
    metric: str
    dimension_key: str
    value: float
    dimensions: dict[str, Any]

class CareerForecastRequest(BaseModel):
    target_country: str = Field(default="USA", min_length=2, max_length=3)
    target_roles: list[str] = Field(default_factory=list, max_length=20)
    max_scenarios: int = Field(default=5, ge=1, le=10)


class CareerPathScenario(BaseModel):
    occupation_code: str
    occupation_title: str
    fit_score: float
    current_skill_overlap: list[str]
    skill_gaps: list[str]
    transition_effort: str
    evidence_sources: list[str]
    warning: str


class CareerForecastResponse(BaseModel):
    forecast_id: str
    method_version: str
    data_version: str
    scenarios: list[CareerPathScenario]
    disclaimer: str


class LearningPlanRequest(BaseModel):
    occupation_code: str = Field(min_length=1, max_length=100)
    occupation_title: str = Field(min_length=1, max_length=1000)
    required_skills: list[str] = Field(default_factory=list, max_length=100)
    country_code: str = Field(default="", max_length=3)


class LearningPlanStep(BaseModel):
    skill: str
    reason: str
    approved_pathways: list[dict[str, str]]


class LearningPlanResponse(BaseModel):
    plan_id: str
    target_occupation_code: str
    target_occupation_title: str
    existing_skills: list[str]
    gaps: list[str]
    steps: list[LearningPlanStep]
    warning: str


class SalaryBenchmarkIn(BaseModel):
    source: str = Field(min_length=2, max_length=200)
    data_vintage: str = Field(min_length=2, max_length=100)
    country_code: str = Field(min_length=2, max_length=3)
    region_code: str = Field(default="", max_length=100)
    occupation_code: str = Field(min_length=1, max_length=100)
    occupation_title: str = Field(min_length=1, max_length=1000)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    wage_p10: float | None = Field(default=None, ge=0)
    wage_p25: float | None = Field(default=None, ge=0)
    wage_median: float | None = Field(default=None, ge=0)
    wage_p75: float | None = Field(default=None, ge=0)
    wage_p90: float | None = Field(default=None, ge=0)
    annual_mean: float | None = Field(default=None, ge=0)
    employment: float | None = Field(default=None, ge=0)
    source_url: str = Field(default="", max_length=3000)
    license: str = Field(default="", max_length=500)


class SalaryBenchmarkResponse(SalaryBenchmarkIn):
    id: str
    captured_at: datetime


class EducationPathwayIn(BaseModel):
    source: str = Field(min_length=2, max_length=200)
    external_id: str = Field(min_length=1, max_length=1000)
    title: str = Field(min_length=1, max_length=1000)
    provider: str = Field(default="", max_length=500)
    pathway_type: Literal["course", "certification", "degree", "license", "apprenticeship", "other"]
    country_code: str = Field(default="", max_length=3)
    occupation_code: str = Field(default="", max_length=100)
    skills: list[str] = Field(default_factory=list, max_length=100)
    description: str = Field(default="", max_length=10_000)
    source_url: str = Field(default="", max_length=3000)
    license: str = Field(default="", max_length=500)


class MobilityMappingIn(BaseModel):
    source: str = Field(min_length=2, max_length=200)
    from_country: str = Field(min_length=2, max_length=3)
    from_occupation_code: str = Field(min_length=1, max_length=100)
    from_title: str = Field(min_length=1, max_length=1000)
    to_country: str = Field(min_length=2, max_length=3)
    to_occupation_code: str = Field(min_length=1, max_length=100)
    to_title: str = Field(min_length=1, max_length=1000)
    common_taxonomy: str = Field(default="ISCO-08", max_length=100)
    common_code: str = Field(default="", max_length=100)
    skill_overlap: float = Field(default=0.0, ge=0, le=1)
    transition_effort: Literal["low", "moderate", "high", "unknown"] = "unknown"
    evidence: dict[str, Any] = Field(default_factory=dict)
    source_url: str = Field(default="", max_length=3000)


class FairnessGroupCount(BaseModel):
    group: str = Field(min_length=1, max_length=200)
    eligible: int = Field(ge=0)
    selected: int = Field(ge=0)


class FairnessAnalysisRequest(BaseModel):
    process_name: str = Field(min_length=2, max_length=200)
    reference_group: str = Field(min_length=1, max_length=200)
    groups: list[FairnessGroupCount] = Field(min_length=2, max_length=30)
    minimum_group_size: int = Field(default=20, ge=10, le=10_000)
    review_ratio_threshold: float = Field(default=0.8, gt=0, le=1)


class FairnessGroupResult(BaseModel):
    group: str
    eligible: int
    selected: int
    selection_rate: float
    rate_ratio: float | None
    suppressed: bool


class FairnessAnalysisResponse(BaseModel):
    snapshot_id: str
    metric: str
    reference_group: str
    groups: list[FairnessGroupResult]
    requires_review: bool
    disclaimer: str


class HumanReviewCreate(BaseModel):
    organization_id: str | None = None
    category: Literal["policy", "evaluation", "fairness", "privacy", "security", "employment"]
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    subject_type: str = Field(min_length=1, max_length=100)
    subject_id: str = Field(default="", max_length=200)
    reason: str = Field(min_length=3, max_length=10_000)
    context: dict[str, Any] = Field(default_factory=dict)


class HumanReviewUpdate(BaseModel):
    status: Literal["open", "in_review", "approved", "rejected", "resolved"]
    resolution: str = Field(default="", max_length=10_000)


class EvalCase(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    category: Literal[
        "unsupported_numbers",
        "unverified_skill",
        "protected_trait_leakage",
        "evidence_required",
        "policy_boundary",
    ]
    input: dict[str, Any] = Field(default_factory=dict)
    candidate_output: dict[str, Any] = Field(default_factory=dict)
    expected_pass: bool = True


class EvalSuiteCreate(BaseModel):
    name: str = Field(min_length=2, max_length=300)
    version: str = Field(min_length=1, max_length=100)
    cases: list[EvalCase] = Field(min_length=1, max_length=1000)


class EvalRunResponse(BaseModel):
    id: str
    suite_id: str
    model_name: str
    status: str
    passed: int
    failed: int
    score: float
    results: list[dict[str, Any]]


class ComplianceDashboardResponse(BaseModel):
    organization_id: str
    open_reviews: int
    critical_reviews: int
    latest_eval_score: float | None
    fairness_reviews_open: int
    evidence_controls_last_30_days: int
    evidence_freshness_days: int | None
    note: str

class CredentialImportRequest(BaseModel):
    credential: dict[str, Any]
    verifier: Literal["none", "configured_remote"] = "none"


class CredentialResponse(BaseModel):
    id: str
    credential_format: str
    credential_type: str
    title: str
    issuer_name: str
    issuer_url: str
    verification_level: str
    verification_status: str
    verification_method: str
    skills: list[str]
    issued_at: datetime | None
    expires_at: datetime | None
    evidence: dict[str, Any]
    created_at: datetime


class LearningProviderConnectionRequest(BaseModel):
    provider: Literal[
        "open_edx",
        "udemy_business",
        "coursera_enterprise",
        "generic_authorized_catalog",
    ]
    base_url: str = Field(min_length=8, max_length=3000)
    credentials: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class LearningProviderConnectionResponse(BaseModel):
    id: str
    organization_id: str
    provider: str
    base_url: str
    enabled: bool
    last_sync_at: datetime | None
    metadata: dict[str, Any]


class LearningCatalogItemResponse(BaseModel):
    id: str
    provider: str
    external_id: str
    title: str
    description: str
    learning_type: str
    skills: list[str]
    level: str
    language: str
    duration_hours: float | None
    credential_offered: bool
    source_url: str
    provenance: dict[str, Any]


class LaborObservationIn(BaseModel):
    source: str = Field(min_length=2, max_length=200)
    data_vintage: str = Field(min_length=2, max_length=100)
    country_code: str = Field(min_length=2, max_length=3)
    region_code: str = Field(default="", max_length=100)
    occupation_code: str = Field(min_length=1, max_length=100)
    occupation_title: str = Field(min_length=1, max_length=1000)
    metric: Literal[
        "employment",
        "openings",
        "wage_median",
        "annual_mean_wage",
        "unemployment_rate",
        "vacancy_rate",
        "custom",
    ]
    period: str = Field(min_length=4, max_length=50)
    value: float
    unit: str = Field(default="", max_length=100)
    source_url: str = Field(min_length=8, max_length=3000)
    license: str = Field(default="", max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LaborTrendRequest(BaseModel):
    source: str = Field(min_length=2, max_length=200)
    country_code: str = Field(min_length=2, max_length=3)
    region_code: str = Field(default="", max_length=100)
    occupation_code: str = Field(min_length=1, max_length=100)
    metric: str = Field(min_length=2, max_length=100)


class LaborTrendResponse(BaseModel):
    id: str
    source: str
    country_code: str
    region_code: str
    occupation_code: str
    occupation_title: str
    metric: str
    method_version: str
    input_count: int
    start_period: str
    end_period: str
    start_value: float
    end_value: float
    linear_slope: float
    annualized_change: float | None
    volatility: float
    direction: str
    confidence: float
    projected_next_value: float | None
    provenance: dict[str, Any]
    disclaimer: str


class PortfolioProject(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=5000)
    url: str = Field(default="", max_length=3000)
    skills: list[str] = Field(default_factory=list, max_length=50)


class PortfolioRequest(BaseModel):
    headline: str = Field(default="", max_length=500)
    about: str = Field(default="", max_length=5000)
    projects: list[PortfolioProject] = Field(default_factory=list, max_length=100)
    links: list[str] = Field(default_factory=list, max_length=30)
    include_verified_credentials: bool = True


class PortfolioResponse(BaseModel):
    id: str
    version: int
    portfolio: dict[str, Any]
    updated_at: datetime


class PortfolioShareRequest(BaseModel):
    expires_in_days: int = Field(default=30, ge=1, le=365)
    include_contact: bool = False
    include_experience: bool = True
    include_education: bool = True
    include_skills: bool = True
    include_credentials: bool = True
    include_projects: bool = True


class PortfolioShareResponse(BaseModel):
    share_id: str
    token: str
    public_path: str
    expires_at: datetime


class AISystemInventoryIn(BaseModel):
    system_key: str = Field(min_length=2, max_length=200)
    version: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=2, max_length=500)
    owner: str = Field(default="", max_length=500)
    intended_purpose: str = Field(min_length=10, max_length=20_000)
    operator_role: Literal["provider", "deployer", "both", "internal"] = "deployer"
    lifecycle_status: Literal[
        "design",
        "development",
        "validation",
        "production",
        "retired",
    ] = "development"
    jurisdictions: list[str] = Field(default_factory=list, max_length=100)
    model_names: list[str] = Field(default_factory=list, max_length=100)
    data_categories: list[str] = Field(default_factory=list, max_length=100)
    employment_use: bool = False
    education_use: bool = False
    profiles_natural_persons: bool = False
    materially_influences_decisions: bool = False
    human_oversight: bool = True
    iso42001_in_scope: bool = True


class AISystemInventoryResponse(AISystemInventoryIn):
    id: str
    organization_id: str
    eu_risk_class: str
    eu_classification_basis: dict[str, Any]
    applicable_from: str | None
    last_reviewed_at: datetime | None
    created_at: datetime


class AIRiskAssessmentIn(BaseModel):
    assessment_version: str = Field(min_length=1, max_length=100)
    likelihood: int = Field(ge=1, le=5)
    impact: int = Field(ge=1, le=5)
    residual_score: int = Field(ge=1, le=25)
    hazards: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    controls: list[dict[str, Any]] = Field(default_factory=list, max_length=200)
    status: Literal["draft", "in_review", "approved"] = "draft"


class AIRiskAssessmentResponse(BaseModel):
    id: str
    inventory_id: str
    assessment_version: str
    likelihood: int
    impact: int
    inherent_score: int
    residual_score: int
    risk_level: str
    hazards: list[dict[str, Any]]
    controls: list[dict[str, Any]]
    status: str
    created_at: datetime
    approved_at: datetime | None


class AIIncidentCreate(BaseModel):
    inventory_id: str | None = None
    severity: Literal["low", "medium", "high", "critical"]
    category: Literal[
        "bias",
        "privacy",
        "security",
        "accuracy",
        "availability",
        "human_oversight",
        "transparency",
        "data_quality",
        "other",
    ]
    serious_incident_candidate: bool = False
    detected_at: datetime
    details: dict[str, Any]


class AIIncidentUpdate(BaseModel):
    status: Literal[
        "open",
        "investigating",
        "contained",
        "remediating",
        "closed",
    ]
    serious_incident_candidate: bool | None = None
    contained_at: datetime | None = None
    closed_at: datetime | None = None
    external_reported_at: datetime | None = None
    details: dict[str, Any] | None = None


class AIIncidentResponse(BaseModel):
    id: str
    organization_id: str
    inventory_id: str | None
    severity: str
    category: str
    status: str
    serious_incident_candidate: bool
    detected_at: datetime
    contained_at: datetime | None
    closed_at: datetime | None
    external_reported_at: datetime | None
    details: dict[str, Any]


class ControlMappingUpdate(BaseModel):
    implementation_status: Literal[
        "not_started",
        "planned",
        "implemented",
        "verified",
        "not_applicable",
    ]
    owner: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=10_000)


class Phase8GovernanceDashboard(BaseModel):
    organization_id: str
    ai_systems: int
    employment_systems: int
    eu_review_required: int
    risk_assessments_open: int
    high_residual_risks: int
    open_incidents: int
    serious_incident_candidates: int
    controls_by_status: dict[str, int]
    evidence_records_last_30_days: int
    note: str

class BLSSeriesImportRequest(BaseModel):
    series_id: str = Field(min_length=3, max_length=100)
    start_year: int = Field(ge=1990, le=2100)
    end_year: int = Field(ge=1990, le=2100)
    country_code: str = Field(default="USA", min_length=2, max_length=3)
    region_code: str = Field(default="", max_length=100)
    occupation_code: str = Field(min_length=1, max_length=100)
    occupation_title: str = Field(min_length=1, max_length=1000)
    metric: str = Field(min_length=2, max_length=100)
    unit: str = Field(default="", max_length=100)
    data_vintage: str = Field(min_length=2, max_length=100)

