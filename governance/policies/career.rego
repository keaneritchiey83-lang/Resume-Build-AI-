package globalcareer

default decision := {
  "allow": true,
  "reasons": [],
}

decision := result if {
  input.action == "job.auto_apply"
  result := {
    "allow": false,
    "reasons": ["Autonomous job application is prohibited."],
  }
} else := result if {
  input.action == "employer.auto_message"
  result := {
    "allow": false,
    "reasons": ["Autonomous employer messaging is prohibited."],
  }
} else := result if {
  protected_ranking_feature
  result := {
    "allow": false,
    "reasons": ["Protected traits cannot be used as ranking features."],
  }
} else := result if {
  input.action == "salary.publish"
  not input.context.source_url
  result := {
    "allow": false,
    "reasons": ["Salary intelligence requires source provenance."],
  }
} else := result if {
  input.action == "career.forecast"
  not input.context.consent
  result := {
    "allow": false,
    "reasons": ["Career forecasting requires active candidate consent."],
  }
} else := result if {
  input.action == "model.release"
  not input.context.eval_passed
  result := {
    "allow": false,
    "reasons": ["Model release requires a passing evaluation gate."],
  }
} else := result if {
  input.action == "credential.claim_as_verified"
  input.context.verification_level != "cryptographic"
  result := {
    "allow": false,
    "reasons": ["Credentials cannot be represented as verified without cryptographic verification."],
  }
} else := result if {
  input.action == "portfolio.share_contact"
  not input.context.explicit_contact_sharing
  result := {
    "allow": false,
    "reasons": ["Public portfolio contact sharing requires an explicit candidate choice."],
  }
} else := result if {
  input.action == "ai.employment.release"
  input.context.eu_risk_class == "annex_iii_high_risk_candidate"
  not input.context.human_oversight
  result := {
    "allow": false,
    "reasons": ["Employment decision AI cannot pass the release gate without human oversight."],
  }
} else := result if {
  input.action == "ai.employment.release"
  input.context.eu_risk_class == "annex_iii_high_risk_candidate"
  not input.context.risk_assessment_approved
  result := {
    "allow": false,
    "reasons": ["High-risk-candidate employment AI requires an approved risk assessment before release."],
  }
} else := result if {
  input.action == "wallet.private_key.store"
  result := {
    "allow": false,
    "reasons": ["The platform must not custody candidate wallet private keys."],
  }
} else := result if {
  input.action == "portable_record.claim_as_verified"
  not input.context.cryptographic_proof_verified
  result := {
    "allow": false,
    "reasons": ["Portable career records cannot be represented as verified without a valid cryptographic proof."],
  }
} else := result if {
  input.action == "dsar.complete"
  input.context.request_type in {"access", "portability", "erasure"}
  not input.context.identity_verified
  result := {
    "allow": false,
    "reasons": ["Privacy-rights requests involving disclosure or deletion require identity verification."],
  }
} else := result if {
  input.action == "retention.delete"
  input.context.legal_hold
  result := {
    "allow": false,
    "reasons": ["Retention deletion is blocked while a legal hold is active."],
  }
} else := result if {
  input.action == "ai.release"
  input.context.red_team_failed
  result := {
    "allow": false,
    "reasons": ["AI release is blocked while red-team findings remain failed."],
  }
} else := result if {
  input.action == "credential.issuer.activate"
  not input.context.platform_approved
  result := {
    "allow": false,
    "reasons": ["Credential issuers require platform approval before activation."],
  }
} else := result if {
  input.action == "credential.verifier.activate"
  not input.context.platform_approved
  result := {
    "allow": false,
    "reasons": ["Credential verifiers require platform approval before activation."],
  }
} else := result if {
  input.action == "credential.issuer_private_key.export"
  result := {
    "allow": false,
    "reasons": ["Issuer private signing keys cannot be exported through application APIs."],
  }
} else := result if {
  input.action == "credential.trust_anchor.dynamic_fetch"
  result := {
    "allow": false,
    "reasons": ["Verifier trust anchors cannot be populated by arbitrary runtime URL fetching."],
  }
} else := result if {
  input.action == "privacy.analytics.release"
  not input.context.minimum_group_met
  result := {
    "allow": false,
    "reasons": ["Privacy analytics must suppress groups below the minimum cohort size."],
  }
} else := result if {
  input.action == "privacy.analytics.release"
  not input.context.epsilon_budget_available
  result := {
    "allow": false,
    "reasons": ["Privacy analytics cannot exceed the configured epsilon budget."],
  }
} else := result if {
  input.action == "audit.delete"
  result := {
    "allow": false,
    "reasons": ["Cryptographic audit entries are append-only."],
  }
} else := result if {
  input.action == "trust.peer_bundle.activate"
  not input.context.bundle_digest_pinned
  result := {
    "allow": false,
    "reasons": ["Cross-region trust requires a pinned peer-bundle digest."],
  }
} else := result if {
  input.action == "trust.peer_bundle.activate"
  not input.context.operator_verified
  result := {
    "allow": false,
    "reasons": ["Cross-region trust requires explicit operator verification."],
  }
} else := result if {
  input.action == "dr.trust_restore"
  not input.context.snapshot_valid
  result := {
    "allow": false,
    "reasons": ["Trust continuity restore requires a valid sealed snapshot."],
  }
} else := result if {
  input.action == "dr.trust_restore"
  not input.context.human_approved
  result := {
    "allow": false,
    "reasons": ["Trust continuity restore requires human approval."],
  }
} else := result if {
  input.action == "transparency.delete"
  result := {
    "allow": false,
    "reasons": ["Phase 13 transparency entries are append-only."],
  }
} else := result if {
  input.action == "model.gateway.tools.enable"
  result := {
    "allow": false,
    "reasons": ["The Phase 13 model gateway does not expose tools."],
  }
} else := result if {
  input.action == "model.release.approve"
  not input.context.eval_passed
  result := {
    "allow": false,
    "reasons": ["A Phase 13 model release requires a passing evaluation."],
  }
} else := result if {
  input.action == "model.release.approve"
  not input.context.signature_present
  result := {
    "allow": false,
    "reasons": ["A production model release requires a release signature."],
  }
} else := result if {
  input.action == "rag.context.include"
  input.context.injection_decision == "block"
  result := {
    "allow": false,
    "reasons": ["Blocked untrusted content cannot enter confidential RAG context."],
  }
} else := result if {
  input.action == "agent.action.execute"
  not input.context.manifest_allows
  result := {
    "allow": false,
    "reasons": ["Agent actions require an active permission manifest."],
  }
} else := result if {
  input.action == "agent.action.execute"
  input.context.requires_human_approval
  not input.context.human_approved
  result := {
    "allow": false,
    "reasons": ["This agent action requires human approval."],
  }
} else := {
  "allow": true,
  "reasons": [],
}

protected_ranking_feature if {
  feature := input.context.ranking_features[_]
  lower(feature) in {
    "race",
    "ethnicity",
    "religion",
    "disability",
    "pregnancy",
    "sexual orientation",
    "gender identity",
    "genetic information",
    "national origin",
  }
}
