# Phase 13 cross-cloud workload identity

Phase 13 extends the SPIFFE/SPIRE boundary from Phase 12 into cross-cloud credential
exchange. The design goal is that workloads use short-lived SPIFFE identities and cloud
STS/token exchange rather than embedding AWS access keys, Azure client secrets, or
long-lived certificates.

## Trust model

1. SPIRE is the workload identity authority inside the deployment.
2. Each workload receives a narrow SPIFFE ID based on namespace/service account.
3. Cloud providers trust a published SPIRE OIDC discovery endpoint through explicit
   administrator configuration.
4. The workload obtains a short-lived JWT-SVID for the exact cloud token-exchange
   audience.
5. The cloud provider validates the JWT-SVID and returns short-lived cloud credentials.
6. The application never stores the resulting cloud secret as configuration.

The Phase 13 API stores only the metadata necessary to audit this relationship:
SPIFFE ID, target cloud, role/client identifier, audience, issuer, region and status.
It does not store exchanged cloud tokens.

## AWS pattern

Use an IAM OIDC identity provider for the SPIRE OIDC discovery issuer and a narrowly
scoped IAM role. The role trust policy should restrict both issuer audience and subject.

Illustrative trust-policy conditions:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::<account-id>:oidc-provider/<spire-oidc-host>"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "<spire-oidc-host>:aud": "sts.amazonaws.com",
        "<spire-oidc-host>:sub": "spiffe://career.example/ns/career/sa/career-api"
      }
    }
  }]
}
```

The workload requests a JWT-SVID with the expected audience and exchanges it with
AWS STS `AssumeRoleWithWebIdentity`. The returned access key, secret and session token
are temporary credentials and should remain in process memory only.

Use regional STS endpoints where practical and keep the IAM role permissions smaller
than the workload's full application role.

## Microsoft Entra / Azure pattern

Publish the SPIRE OIDC discovery endpoint over HTTPS and configure an Entra federated
identity credential whose:

- issuer is the SPIRE OIDC discovery issuer;
- subject is the exact workload SPIFFE ID;
- audience is `api://AzureADTokenExchange`.

Current Microsoft guidance for SPIFFE/SPIRE federation additionally expects signing
keys to advertise `use: sig`, and its external-issuer flow currently requires RS256
JWT-SVID signing. Verify these provider requirements again at deployment time because
cloud token-exchange constraints can change independently of SPIFFE.

The workload requests a JWT-SVID for `api://AzureADTokenExchange` and exchanges that
assertion for an Entra access token through the standard workload-federation flow.

## Operational requirements

- Publish OIDC discovery only from infrastructure you control.
- Protect its signing-key lifecycle as a security-critical service.
- Use an exact subject match instead of wildcarding every SPIFFE ID in the trust domain.
- Use distinct cloud roles/apps for API, workers, migration jobs and security controllers.
- Rotate SPIRE signing keys according to a tested overlap schedule.
- Log only token metadata/digests; never log JWT-SVIDs or cloud bearer tokens.
- Revoke the cloud federation binding when a workload identity is retired.
- Keep Phase 13 `CrossCloudWorkloadBinding` records synchronized with cloud IAM.
- Test issuer/audience/subject mismatch failures during disaster-recovery exercises.

## Disaster recovery

A trust-continuity snapshot records the configuration and digests needed to reconstruct
the federation relationship, but it does not contain cloud bearer credentials or SPIRE
private signing material. Recovery remains a human-approved process:

1. restore the SPIRE control plane from its separately protected recovery procedure;
2. validate the restored trust-domain bundle;
3. compare it against the last approved Phase 13 trust-continuity snapshot;
4. restore/update cloud OIDC trust only after the bundle/issuer is validated;
5. test a low-privilege workload exchange;
6. explicitly approve production bindings.

Never automatically update a cloud trust relationship merely because a remote bundle
or recovery snapshot exists.
