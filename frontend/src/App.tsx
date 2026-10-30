import { FormEvent, useEffect, useMemo, useState } from "react";

import { API_URL, api } from "./api";


function b64urlToBytes(value: string): Uint8Array {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function bufferToB64url(value: ArrayBuffer | null): string {
  if (!value) return "";
  const bytes = new Uint8Array(value);
  let binary = "";

  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }

  return btoa(binary)
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/g, "");
}

function creationOptionsFromJson(value: any): PublicKeyCredentialCreationOptions {
  return {
    ...value,
    challenge: b64urlToBytes(value.challenge),
    user: {
      ...value.user,
      id: b64urlToBytes(value.user.id),
    },
    excludeCredentials: (value.excludeCredentials ?? []).map((item: any) => ({
      ...item,
      id: b64urlToBytes(item.id),
    })),
  };
}

function requestOptionsFromJson(value: any): PublicKeyCredentialRequestOptions {
  return {
    ...value,
    challenge: b64urlToBytes(value.challenge),
    allowCredentials: (value.allowCredentials ?? []).map((item: any) => ({
      ...item,
      id: b64urlToBytes(item.id),
    })),
  };
}

function registrationCredentialToJson(
  credential: PublicKeyCredential,
): Record<string, unknown> {
  const response = credential.response as AuthenticatorAttestationResponse;

  return {
    id: credential.id,
    rawId: bufferToB64url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment,
    clientExtensionResults: credential.getClientExtensionResults(),
    response: {
      attestationObject: bufferToB64url(response.attestationObject),
      clientDataJSON: bufferToB64url(response.clientDataJSON),
      transports:
        typeof response.getTransports === "function"
          ? response.getTransports()
          : [],
    },
  };
}

function authenticationCredentialToJson(
  credential: PublicKeyCredential,
): Record<string, unknown> {
  const response = credential.response as AuthenticatorAssertionResponse;

  return {
    id: credential.id,
    rawId: bufferToB64url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment,
    clientExtensionResults: credential.getClientExtensionResults(),
    response: {
      authenticatorData: bufferToB64url(response.authenticatorData),
      clientDataJSON: bufferToB64url(response.clientDataJSON),
      signature: bufferToB64url(response.signature),
      userHandle: bufferToB64url(response.userHandle),
    },
  };
}


type User = {
  id: string;
  email: string;
  is_platform_admin: boolean;
  mfa_enabled: boolean;
};

type Job = {
  id: string;
  title: string;
  organization: string;
  location: string;
  description: string;
  apply_url: string;
  match_score: number;
  matched_skills: string[];
};

type Application = {
  id: string;
  job_id: string | null;
  title: string;
  organization: string;
  status: string;
  notes: string;
  created_at: string;
};

type Organization = {
  id: string;
  name: string;
  slug: string;
  role: string;
};

const emptyProfile = {
  full_name: "",
  email: "",
  phone: "",
  location: "",
  summary: "",
  skills: [],
  abilities: [],
  core_values: [],
  experience: [],
  education: [],
  certifications: [],
  publications: [],
};

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    api<User>("/v1/auth/me").then(setUser).catch(() => setUser(null));
  }, []);

  if (!user) {
    return (
      <main className="auth-shell">
        <form
          className="card auth-card"
          onSubmit={async (event) => {
            event.preventDefault();
            setMessage("");

            try {
              if (mode === "register") {
                await api<User>("/v1/auth/register", {
                  method: "POST",
                  body: JSON.stringify({
                    email,
                    password,
                    mfa_code: "",
                  }),
                });
              }

              const account = await api<User>("/v1/auth/login", {
                method: "POST",
                body: JSON.stringify({
                  email,
                  password,
                  mfa_code: mfaCode,
                }),
              });

              setUser(account);
            } catch (error) {
              setMessage(
                error instanceof Error ? error.message : "Request failed.",
              );
            }
          }}
        >
          <h1>Global Career Architecture AI</h1>
          <p>Enterprise-protected career intelligence and hiring workspace.</p>

          <label>
            Email
            <input
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              type="email"
              required
            />
          </label>

          <label>
            Password
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type="password"
              minLength={12}
              required
            />
          </label>

          {mode === "login" && (
            <label>
              MFA code, if enabled
              <input
                value={mfaCode}
                onChange={(event) => setMfaCode(event.target.value)}
                inputMode="numeric"
              />
            </label>
          )}

          <button type="submit">
            {mode === "login" ? "Sign in" : "Create account"}
          </button>

          {mode === "login" && (
            <button
              type="button"
              className="secondary"
              onClick={async () => {
                setMessage("");

                try {
                  if (!window.PublicKeyCredential) {
                    throw new Error("This browser does not support WebAuthn.");
                  }

                  const options = await api<{
                    challenge_id: string;
                    publicKey: any;
                  }>("/v1/phase11/passkeys/login/options", {
                    method: "POST",
                    body: JSON.stringify({ email }),
                  });

                  const credential = (await navigator.credentials.get({
                    publicKey: requestOptionsFromJson(options.publicKey),
                  })) as PublicKeyCredential | null;

                  if (!credential) {
                    throw new Error("Passkey authentication was cancelled.");
                  }

                  const account = await api<User>(
                    "/v1/phase11/passkeys/login/finish",
                    {
                      method: "POST",
                      body: JSON.stringify({
                        challenge_id: options.challenge_id,
                        credential: authenticationCredentialToJson(credential),
                      }),
                    },
                  );

                  setUser(account);
                } catch (error) {
                  setMessage(
                    error instanceof Error
                      ? error.message
                      : "Passkey authentication failed.",
                  );
                }
              }}
            >
              Sign in with passkey
            </button>
          )}

          <button
            type="button"
            className="secondary"
            onClick={() =>
              setMode((current) =>
                current === "login" ? "register" : "login",
              )
            }
          >
            {mode === "login" ? "Create an account" : "Back to sign in"}
          </button>

          <a className="button-link" href={`${API_URL}/v1/auth/oidc/login`}>
            Enterprise SSO
          </a>

          {message && <p className="error">{message}</p>}
        </form>
      </main>
    );
  }

  return (
    <Dashboard
      user={user}
      onUserChange={setUser}
      onLogout={async () => {
        await api("/v1/auth/logout", { method: "POST" });
        setUser(null);
      }}
    />
  );
}

function Dashboard({
  user,
  onUserChange,
  onLogout,
}: {
  user: User;
  onUserChange: (user: User) => void;
  onLogout: () => Promise<void>;
}) {
  const [tab, setTab] = useState("profile");
  const tabs = [
    "profile",
    "jobs",
    "ai",
    "applications",
    "agents",
    "pathways",
    "credentials",
    "portfolio",
    "passport",
    "openid",
    "privacy-engineering",
    "phase11-security",
    "phase12-trust-security",
    "phase13-trust-ai-security",
    "phase14-agents-operations",
    "phase15-17-career-studio",
    "learning",
    "privacy",
    "assurance",
    "organizations",
    "recruiter",
    "governance",
    "webhooks",
    ...(user.is_platform_admin ? ["admin"] : []),
  ];

  return (
    <div className="layout">
      <aside>
        <h2>Career AI</h2>
        <small>{user.email}</small>

        {tabs.map((item) => (
          <button
            key={item}
            className={tab === item ? "nav active" : "nav"}
            onClick={() => setTab(item)}
          >
            {item[0].toUpperCase() + item.slice(1)}
          </button>
        ))}

        <button className="nav" onClick={onLogout}>
          Sign out
        </button>
      </aside>

      <main className="content">
        {tab === "profile" && (
          <ProfilePanel user={user} onUserChange={onUserChange} />
        )}
        {tab === "jobs" && <JobsPanel />}
        {tab === "ai" && <AIPanel />}
        {tab === "applications" && <ApplicationsPanel />}
        {tab === "agents" && <CareerAgentsPanel />}
        {tab === "pathways" && <PathwaysPanel />}
        {tab === "credentials" && <CredentialsPanel />}
        {tab === "portfolio" && <PortfolioPanel />}
        {tab === "passport" && <Phase9PassportPanel />}
        {tab === "openid" && <Phase10IdentityPanel />}
        {tab === "privacy-engineering" && <Phase10PrivacyEngineeringPanel />}
        {tab === "phase11-security" && <Phase11SecurityPanel />}
        {tab === "phase12-trust-security" && <Phase12TrustSecurityPanel />}
        {tab === "phase13-trust-ai-security" && <Phase13TrustAISecurityPanel />}
        {tab === "phase14-agents-operations" && <Phase14AgentsOperationsPanel />}
        {tab === "phase15-17-career-studio" && <Phase1517StudioPanel />}
        {tab === "learning" && <LearningAndTrendsPanel />}
        {tab === "privacy" && <Phase9PrivacyPanel />}
        {tab === "assurance" && <Phase8AssurancePanel />}
        {tab === "organizations" && <OrganizationsPanel />}
        {tab === "recruiter" && <RecruiterPanel />}
        {tab === "governance" && <GovernancePanel />}
        {tab === "webhooks" && <WebhooksPanel />}
        {tab === "admin" && user.is_platform_admin && <AdminPanel />}
      </main>
    </div>
  );
}

function ProfilePanel({
  user,
  onUserChange,
}: {
  user: User;
  onUserChange: (user: User) => void;
}) {
  const [profileText, setProfileText] = useState(
    JSON.stringify(emptyProfile, null, 2),
  );
  const [message, setMessage] = useState("");
  const [mfaSecret, setMfaSecret] = useState("");
  const [mfaUri, setMfaUri] = useState("");
  const [mfaCode, setMfaCode] = useState("");

  useEffect(() => {
    api<Record<string, unknown>>("/v1/profile")
      .then((profile) => setProfileText(JSON.stringify(profile, null, 2)))
      .catch(() => undefined);
  }, []);

  async function saveProfile(event: FormEvent) {
    event.preventDefault();

    try {
      await api("/v1/profile", {
        method: "PUT",
        body: JSON.stringify(JSON.parse(profileText)),
      });
      setMessage("Encrypted profile saved.");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Could not save profile.",
      );
    }
  }

  return (
    <section>
      <h1>Candidate Profile & Security</h1>
      <p>
        Candidate PII is encrypted at rest. Use AWS KMS in production or the
        local keyring for development.
      </p>

      <form onSubmit={saveProfile}>
        <textarea
          className="json-editor"
          value={profileText}
          onChange={(event) => setProfileText(event.target.value)}
        />
        <button type="submit">Save encrypted profile</button>
      </form>

      <h2>Résumé upload</h2>
      <input
        type="file"
        accept=".pdf,.docx,.txt"
        onChange={async (event) => {
          const file = event.target.files?.[0];

          if (!file) return;

          const form = new FormData();
          form.append("resume", file);

          try {
            const result = await api<{ characters_extracted: number }>(
              "/v1/resumes/upload",
              { method: "POST", body: form },
            );
            setMessage(
              `Résumé parsed securely: ${result.characters_extracted} characters extracted.`,
            );
          } catch (error) {
            setMessage(
              error instanceof Error ? error.message : "Upload failed.",
            );
          }
        }}
      />

      <h2>Multi-factor authentication</h2>

      {!user.mfa_enabled ? (
        <>
          <button
            onClick={async () => {
              try {
                const result = await api<{
                  secret: string;
                  provisioning_uri: string;
                }>("/v1/auth/mfa/setup", { method: "POST" });

                setMfaSecret(result.secret);
                setMfaUri(result.provisioning_uri);
              } catch (error) {
                setMessage(
                  error instanceof Error ? error.message : "MFA setup failed.",
                );
              }
            }}
          >
            Start MFA setup
          </button>

          {mfaSecret && (
            <div className="card">
              <p>
                Add this secret to your authenticator and keep it private:
                <br />
                <code>{mfaSecret}</code>
              </p>
              <details>
                <summary>Provisioning URI</summary>
                <code>{mfaUri}</code>
              </details>
              <div className="row">
                <input
                  placeholder="6-digit code"
                  value={mfaCode}
                  onChange={(event) => setMfaCode(event.target.value)}
                />
                <button
                  onClick={async () => {
                    await api("/v1/auth/mfa/confirm", {
                      method: "POST",
                      body: JSON.stringify({ code: mfaCode }),
                    });
                    onUserChange({ ...user, mfa_enabled: true });
                    setMessage("MFA enabled.");
                  }}
                >
                  Confirm MFA
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <p>MFA is enabled for local password sign-in.</p>
      )}


      <h2>Passkeys</h2>
      <p>
        Register a platform authenticator or security key. Private keys remain
        on the authenticator and are never sent to this service.
      </p>
      <button
        onClick={async () => {
          try {
            if (!window.PublicKeyCredential) {
              throw new Error("This browser does not support WebAuthn.");
            }

            const options = await api<{
              challenge_id: string;
              publicKey: any;
            }>("/v1/phase11/passkeys/register/options", {
              method: "POST",
            });

            const credential = (await navigator.credentials.create({
              publicKey: creationOptionsFromJson(options.publicKey),
            })) as PublicKeyCredential | null;

            if (!credential) {
              throw new Error("Passkey registration was cancelled.");
            }

            await api("/v1/phase11/passkeys/register/finish", {
              method: "POST",
              body: JSON.stringify({
                challenge_id: options.challenge_id,
                credential: registrationCredentialToJson(credential),
                nickname: "Browser passkey",
              }),
            });

            setMessage("Passkey registered.");
          } catch (error) {
            setMessage(
              error instanceof Error ? error.message : "Passkey registration failed.",
            );
          }
        }}
      >
        Register passkey
      </button>

      <h2>Encryption key rotation</h2>
      <button
        onClick={async () => {
          const result = await api<{ rotated_records: number }>(
            "/v1/security/rotate-data-keys",
            { method: "POST" },
          );
          setMessage(`Re-encrypted ${result.rotated_records} protected records.`);
        }}
      >
        Rotate my data keys
      </button>

      {message && <p>{message}</p>}
    </section>
  );
}

function JobsPanel() {
  const [query, setQuery] = useState("");
  const [location, setLocation] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [message, setMessage] = useState("");

  async function search(event: FormEvent) {
    event.preventDefault();

    try {
      const params = new URLSearchParams({ q: query, location });
      setJobs(await api<Job[]>(`/v1/jobs/matches?${params}`));
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Search failed.");
    }
  }

  return (
    <section>
      <h1>Job Matching</h1>

      <form className="row" onSubmit={search}>
        <input
          placeholder="Role or keyword"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <input
          placeholder="Location"
          value={location}
          onChange={(event) => setLocation(event.target.value)}
        />
        <button type="submit">Match</button>
      </form>

      {message && <p className="error">{message}</p>}

      <div className="grid">
        {jobs.map((job) => (
          <article className="card" key={job.id}>
            <span className="score">{job.match_score}% profile overlap</span>
            <h3>{job.title}</h3>
            <p>
              {job.organization} · {job.location}
            </p>
            <p>{job.matched_skills.join(", ") || "No direct skill overlap yet."}</p>
            <button
              onClick={async () => {
                await api("/v1/applications", {
                  method: "POST",
                  body: JSON.stringify({
                    job_id: job.id,
                    title: job.title,
                    organization: job.organization || "Unknown",
                    status: "saved",
                    notes: "",
                  }),
                });
                setMessage("Saved to application tracker.");
              }}
            >
              Save job
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}

function AIPanel() {
  const [title, setTitle] = useState("");
  const [organization, setOrganization] = useState("");
  const [description, setDescription] = useState("");
  const [skills, setSkills] = useState("");
  const [result, setResult] = useState("");
  const [working, setWorking] = useState(false);

  const target = useMemo(
    () => ({
      title,
      organization,
      description,
      required_skills: skills
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    }),
    [title, organization, description, skills],
  );

  async function run(path: string) {
    setWorking(true);
    setResult("");

    try {
      const response = await api<Record<string, unknown>>(path, {
        method: "POST",
        body: JSON.stringify({ target, style: "ats" }),
      });
      setResult(JSON.stringify(response, null, 2));
    } catch (error) {
      setResult(error instanceof Error ? error.message : "AI request failed.");
    } finally {
      setWorking(false);
    }
  }

  return (
    <section>
      <h1>AI Career Studio</h1>
      <p>
        Generated claims are checked against the candidate fact ledger before
        they are returned.
      </p>

      <div className="stack">
        <input
          placeholder="Target job title"
          value={title}
          onChange={(event) => setTitle(event.target.value)}
        />
        <input
          placeholder="Organization"
          value={organization}
          onChange={(event) => setOrganization(event.target.value)}
        />
        <input
          placeholder="Required skills, comma separated"
          value={skills}
          onChange={(event) => setSkills(event.target.value)}
        />
        <textarea
          placeholder="Paste the target job description"
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />

        <div className="row">
          <button disabled={working} onClick={() => run("/v1/ai/resume")}>
            Tailor résumé
          </button>
          <button disabled={working} onClick={() => run("/v1/ai/cover-letter")}>
            Cover letter
          </button>
          <button disabled={working} onClick={() => run("/v1/ai/interview-plan")}>
            Interview plan
          </button>
        </div>
      </div>

      <pre>{result}</pre>
    </section>
  );
}

function ApplicationsPanel() {
  const [items, setItems] = useState<Application[]>([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api<Application[]>("/v1/applications")
      .then(setItems)
      .catch((error) =>
        setMessage(error instanceof Error ? error.message : "Could not load."),
      );
  }, []);

  return (
    <section>
      <h1>Application Tracker</h1>
      {message && <p className="error">{message}</p>}

      <div className="grid">
        {items.map((item) => (
          <article className="card" key={item.id}>
            <h3>{item.title}</h3>
            <p>{item.organization}</p>
            <strong>{item.status}</strong>
            {item.notes && <p>{item.notes}</p>}
          </article>
        ))}
      </div>
    </section>
  );
}

function OrganizationsPanel() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selected, setSelected] = useState("");
  const [provider, setProvider] = useState("linkedin");
  const [credentials, setCredentials] = useState("{}");
  const [jobPayload, setJobPayload] = useState(
    JSON.stringify(
      {
        external_job_id: "ats-job-1042",
        title: "Senior Software Engineer",
        description:
          "Build secure software systems and collaborate across engineering teams.",
        location: "Columbus, OH",
        country: "US",
        city_region_postal: "Columbus, OH",
        employer_name: "Example Employer",
        company_website: "https://example.com",
        public_job_url: "https://example.com/jobs/1042",
        apply_url: "https://example.com/jobs/1042/apply",
        poster_email: "recruiting@example.com",
        job_type: "full_time",
        operation: "CREATE",
        provider_job_id: "",
      },
      null,
      2,
    ),
  );
  const [result, setResult] = useState("");

  async function load() {
    const values = await api<Organization[]>("/v1/organizations");
    setOrganizations(values);

    if (!selected && values[0]) {
      setSelected(values[0].id);
    }
  }

  useEffect(() => {
    load().catch(() => undefined);
  }, []);

  return (
    <section>
      <h1>Organizations & Authorized Providers</h1>
      <p>
        Provider credentials are encrypted and never returned after storage.
        LinkedIn, Indeed, and ZipRecruiter adapters activate only with approved
        partner credentials.
      </p>

      <div className="stack">
        <select value={selected} onChange={(event) => setSelected(event.target.value)}>
          {organizations.map((organization) => (
            <option value={organization.id} key={organization.id}>
              {organization.name} ({organization.role})
            </option>
          ))}
        </select>

        <select value={provider} onChange={(event) => setProvider(event.target.value)}>
          <option value="linkedin">LinkedIn Apply Connect</option>
          <option value="indeed">Indeed Job Sync</option>
          <option value="ziprecruiter">ZipRecruiter Partner API</option>
        </select>

        <textarea
          className="json-editor short"
          value={credentials}
          onChange={(event) => setCredentials(event.target.value)}
        />

        <button
          disabled={!selected}
          onClick={async () => {
            try {
              await api(
                `/v1/organizations/${selected}/providers/${provider}/credentials`,
                {
                  method: "PUT",
                  body: JSON.stringify({
                    credentials: JSON.parse(credentials),
                    enabled: true,
                  }),
                },
              );
              setCredentials("{}");
              setResult("Provider credentials encrypted and stored.");
            } catch (error) {
              setResult(
                error instanceof Error ? error.message : "Provider setup failed.",
              );
            }
          }}
        >
          Save encrypted provider credentials
        </button>

        <button
          className="secondary"
          disabled={!selected}
          onClick={async () => {
            const response = await api(
              `/v1/organizations/${selected}/security/rotate-provider-keys`,
              { method: "POST" },
            );
            setResult(JSON.stringify(response, null, 2));
          }}
        >
          Rotate provider encryption keys
        </button>

        <h2>Authorized provider job operation</h2>
        <textarea
          className="json-editor short"
          value={jobPayload}
          onChange={(event) => setJobPayload(event.target.value)}
        />
        <button
          disabled={!selected}
          onClick={async () => {
            try {
              const response = await api<Record<string, unknown>>(
                `/v1/organizations/${selected}/providers/${provider}/jobs`,
                {
                  method: "POST",
                  body: JSON.stringify(JSON.parse(jobPayload)),
                },
              );
              setResult(JSON.stringify(response, null, 2));
            } catch (error) {
              setResult(
                error instanceof Error
                  ? error.message
                  : "Provider job operation failed.",
              );
            }
          }}
        >
          Submit authorized provider operation
        </button>
      </div>

      <pre>{result}</pre>
    </section>
  );
}


function WebhooksPanel() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selected, setSelected] = useState("");
  const [events, setEvents] = useState<Record<string, unknown>[]>([]);
  const [candidates, setCandidates] = useState<Record<string, unknown>[]>([]);
  const [applications, setApplications] = useState<Record<string, unknown>[]>([]);
  const [attachments, setAttachments] = useState<Record<string, unknown>[]>([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api<Organization[]>("/v1/organizations")
      .then((values) => {
        setOrganizations(values);
        if (values[0]) setSelected(values[0].id);
      })
      .catch((error) =>
        setMessage(error instanceof Error ? error.message : "Could not load organizations."),
      );
  }, []);

  async function refresh() {
    if (!selected) return;

    try {
      const [nextEvents, nextCandidates, nextApplications, nextAttachments] =
        await Promise.all([
          api<Record<string, unknown>[]>(
            `/v1/organizations/${selected}/webhooks/events?limit=50`,
          ),
          api<Record<string, unknown>[]>(
            `/v1/organizations/${selected}/inbound-candidates?limit=50`,
          ),
          api<Record<string, unknown>[]>(
            `/v1/organizations/${selected}/inbound-applications?limit=50`,
          ),
          api<Record<string, unknown>[]>(
            `/v1/organizations/${selected}/inbound-attachments?limit=50`,
          ),
        ]);

      setEvents(nextEvents);
      setCandidates(nextCandidates);
      setApplications(nextApplications);
      setAttachments(nextAttachments);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Webhook view failed.");
    }
  }

  useEffect(() => {
    refresh();
  }, [selected]);

  return (
    <section>
      <h1>Application Webhooks</h1>
      <p>
        Verified provider deliveries are stored in a durable encrypted inbox,
        deduplicated, and processed asynchronously by the worker.
      </p>

      <div className="row">
        <select value={selected} onChange={(event) => setSelected(event.target.value)}>
          {organizations.map((organization) => (
            <option value={organization.id} key={organization.id}>
              {organization.name}
            </option>
          ))}
        </select>
        <button onClick={refresh} disabled={!selected}>
          Refresh
        </button>
      </div>

      {message && <p className="error">{message}</p>}

      <h2>Recent webhook events</h2>
      <pre>{JSON.stringify(events, null, 2)}</pre>

      <h2>Inbound candidates</h2>
      <pre>{JSON.stringify(candidates, null, 2)}</pre>

      <h2>Inbound applications</h2>
      <pre>{JSON.stringify(applications, null, 2)}</pre>

      <h2>Encrypted attachments</h2>
      <pre>{JSON.stringify(attachments, null, 2)}</pre>
    </section>
  );
}



type Recommendation = {
  id: string;
  job_id: string;
  title: string;
  organization: string;
  location: string;
  apply_url: string;
  score: number;
  state: string;
  matched_skills: string[];
  reasons: string[];
  evaluated_at: string;
  notified_at: string | null;
  agent_analyzed_at: string | null;
};

function CareerAgentsPanel() {
  const [enabled, setEnabled] = useState(false);
  const [aiAnalysis, setAiAnalysis] = useState(false);
  const [notifications, setNotifications] = useState(true);
  const [roles, setRoles] = useState("");
  const [locations, setLocations] = useState("");
  const [threshold, setThreshold] = useState(65);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [result, setResult] = useState("");

  async function loadRecommendations() {
    try {
      setRecommendations(
        await api<Recommendation[]>("/v1/agent/recommendations?limit=50"),
      );
    } catch {
      setRecommendations([]);
    }
  }

  useEffect(() => {
    api<Record<string, unknown>>("/v1/agent/monitoring-policy")
      .then((policy) => {
        setEnabled(Boolean(policy.enabled));
        const purposes = Array.isArray(policy.purposes)
          ? (policy.purposes as string[])
          : [];
        setAiAnalysis(purposes.includes("ai_career_analysis"));
        setNotifications(purposes.includes("in_app_notifications"));
        setRoles(
          Array.isArray(policy.target_roles)
            ? (policy.target_roles as string[]).join(", ")
            : "",
        );
        setLocations(
          Array.isArray(policy.target_locations)
            ? (policy.target_locations as string[]).join(", ")
            : "",
        );
        setThreshold(Number(policy.minimum_match_score ?? 65));
      })
      .catch(() => undefined);

    loadRecommendations();
  }, []);

  async function savePolicy() {
    const purposes = ["job_monitoring"];

    if (aiAnalysis) purposes.push("ai_career_analysis");
    if (notifications) purposes.push("in_app_notifications");

    try {
      await api("/v1/agent/monitoring-policy", {
        method: "PUT",
        body: JSON.stringify({
          enabled,
          acknowledged: enabled,
          purposes: enabled ? purposes : [],
          target_roles: roles
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean),
          target_locations: locations
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean),
          remote_preference: "any",
          minimum_match_score: threshold,
          cadence: "daily",
          max_alerts_per_scan: 20,
        }),
      });
      setResult(enabled ? "Monitoring consent saved." : "Monitoring revoked.");
    } catch (error) {
      setResult(error instanceof Error ? error.message : "Could not save policy.");
    }
  }

  return (
    <section>
      <h1>Career Agents & Job Monitor</h1>
      <p>
        Monitoring is opt-in. Agents can analyze and coach, but cannot apply to
        jobs, contact employers, or change verified profile facts.
      </p>

      <div className="card stack">
        <label className="check-row">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(event) => setEnabled(event.target.checked)}
          />
          Enable automated job monitoring
        </label>

        <label>
          Target roles, comma separated
          <input value={roles} onChange={(event) => setRoles(event.target.value)} />
        </label>

        <label>
          Target locations, comma separated
          <input
            value={locations}
            onChange={(event) => setLocations(event.target.value)}
          />
        </label>

        <label>
          Minimum match score: {threshold}
          <input
            type="range"
            min="0"
            max="100"
            value={threshold}
            onChange={(event) => setThreshold(Number(event.target.value))}
          />
        </label>

        <label className="check-row">
          <input
            type="checkbox"
            checked={aiAnalysis}
            onChange={(event) => setAiAnalysis(event.target.checked)}
          />
          Allow AI career analysis of matched jobs
        </label>

        <label className="check-row">
          <input
            type="checkbox"
            checked={notifications}
            onChange={(event) => setNotifications(event.target.checked)}
          />
          Allow in-app match notifications
        </label>

        <div className="row">
          <button onClick={savePolicy}>Save consent & preferences</button>
          <button
            className="secondary"
            disabled={!enabled}
            onClick={async () => {
              try {
                const response = await api<Record<string, unknown>>(
                  "/v1/agent/monitor/scan",
                  { method: "POST" },
                );
                setResult(JSON.stringify(response, null, 2));
                await loadRecommendations();
              } catch (error) {
                setResult(
                  error instanceof Error ? error.message : "Scan failed.",
                );
              }
            }}
          >
            Scan now
          </button>
        </div>
      </div>

      {result && <pre>{result}</pre>}

      <div className="grid">
        {recommendations.map((recommendation) => (
          <article className="card" key={recommendation.id}>
            <span className="score">{recommendation.score}% monitored fit</span>
            <h3>{recommendation.title}</h3>
            <p>
              {recommendation.organization} · {recommendation.location}
            </p>
            <p>{recommendation.matched_skills.join(", ")}</p>
            <ul>
              {recommendation.reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
            <div className="row">
              <button
                disabled={!aiAnalysis}
                onClick={async () => {
                  try {
                    const response = await api<Record<string, unknown>>(
                      "/v1/agent/runs",
                      {
                        method: "POST",
                        body: JSON.stringify({
                          recommendation_id: recommendation.id,
                        }),
                      },
                    );
                    setResult(JSON.stringify(response, null, 2));
                    await loadRecommendations();
                  } catch (error) {
                    setResult(
                      error instanceof Error
                        ? error.message
                        : "Agent analysis failed.",
                    );
                  }
                }}
              >
                Run bounded agent team
              </button>
              <button
                className="secondary"
                onClick={async () => {
                  await api(`/v1/agent/recommendations/${recommendation.id}`, {
                    method: "PATCH",
                    body: JSON.stringify({ state: "dismissed" }),
                  });
                  await loadRecommendations();
                }}
              >
                Dismiss
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

type RecruiterDashboard = {
  organization_id: string;
  candidates: number;
  applications: number;
  applications_last_30_days: number;
  by_stage: Record<string, number>;
  by_source: Record<string, number>;
  webhook_dead_letters: number;
};

type RecruiterRow = {
  application_id: string;
  candidate_id: string;
  full_name: string;
  email: string;
  provider: string;
  external_job_id: string;
  source_attribution: string;
  status: string;
  received_at: string;
  processing_basis: string;
  privacy_notice_version: string;
};

function RecruiterPanel() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [dashboard, setDashboard] = useState<RecruiterDashboard | null>(null);
  const [pipeline, setPipeline] = useState<RecruiterRow[]>([]);
  const [analytics, setAnalytics] = useState<Record<string, unknown>[]>([]);
  const [message, setMessage] = useState("");

  useEffect(() => {
    api<Organization[]>("/v1/organizations")
      .then((values) => {
        const recruiterOrganizations = values.filter((organization) =>
          ["owner", "admin", "recruiter"].includes(organization.role),
        );
        setOrganizations(recruiterOrganizations);

        if (recruiterOrganizations[0]) {
          setOrganizationId(recruiterOrganizations[0].id);
        }
      })
      .catch(() => undefined);
  }, []);

  async function load(selected = organizationId) {
    if (!selected) return;

    try {
      const [summary, candidates, series] = await Promise.all([
        api<RecruiterDashboard>(
          `/v1/organizations/${selected}/recruiter/dashboard`,
        ),
        api<RecruiterRow[]>(
          `/v1/organizations/${selected}/recruiter/pipeline?limit=100`,
        ),
        api<Record<string, unknown>[]>(
          `/v1/organizations/${selected}/analytics?days=30`,
        ),
      ]);

      setDashboard(summary);
      setPipeline(candidates);
      setAnalytics(series);
      setMessage("");
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Recruiter dashboard failed.",
      );
    }
  }

  useEffect(() => {
    load();
  }, [organizationId]);

  return (
    <section>
      <h1>Recruiter Dashboard</h1>
      <p>
        Candidate records are organization-scoped. Protected/self-identification
        attributes are excluded from matching and ranking workflows.
      </p>

      <select
        value={organizationId}
        onChange={(event) => setOrganizationId(event.target.value)}
      >
        {organizations.map((organization) => (
          <option value={organization.id} key={organization.id}>
            {organization.name} ({organization.role})
          </option>
        ))}
      </select>

      {message && <p className="error">{message}</p>}

      {dashboard && (
        <div className="metric-grid">
          <div className="metric-card">
            <strong>{dashboard.candidates}</strong>
            <span>Candidates</span>
          </div>
          <div className="metric-card">
            <strong>{dashboard.applications}</strong>
            <span>Applications</span>
          </div>
          <div className="metric-card">
            <strong>{dashboard.applications_last_30_days}</strong>
            <span>Last 30 days</span>
          </div>
          <div className="metric-card">
            <strong>{dashboard.webhook_dead_letters}</strong>
            <span>Dead letters</span>
          </div>
        </div>
      )}

      <h2>Pipeline</h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Source</th>
              <th>Job</th>
              <th>Stage</th>
              <th>Processing basis</th>
            </tr>
          </thead>
          <tbody>
            {pipeline.map((row) => (
              <tr key={row.application_id}>
                <td>
                  {row.full_name}
                  <br />
                  <small>{row.email}</small>
                </td>
                <td>{row.source_attribution || row.provider}</td>
                <td>{row.external_job_id}</td>
                <td>
                  <select
                    value={row.status}
                    onChange={async (event) => {
                      await api(
                        `/v1/organizations/${organizationId}/recruiter/applications/${row.application_id}`,
                        {
                          method: "PATCH",
                          body: JSON.stringify({ status: event.target.value }),
                        },
                      );
                      await load();
                    }}
                  >
                    {[
                      "received",
                      "review",
                      "screen",
                      "interview",
                      "offer",
                      "hired",
                      "rejected",
                      "withdrawn",
                    ].map((stage) => (
                      <option value={stage} key={stage}>
                        {stage}
                      </option>
                    ))}
                  </select>
                </td>
                <td>{row.processing_basis}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>30-day aggregate analytics</h2>
      <pre>{JSON.stringify(analytics, null, 2)}</pre>
    </section>
  );
}


function PathwaysPanel() {
  const [targetRoles, setTargetRoles] = useState("");
  const [country, setCountry] = useState("USA");
  const [occupation, setOccupation] = useState("");
  const [salaryResult, setSalaryResult] = useState("");
  const [forecastResult, setForecastResult] = useState("");

  async function forecast() {
    try {
      const result = await api<Record<string, unknown>>("/v1/career/forecast", {
        method: "POST",
        body: JSON.stringify({
          target_country: country,
          target_roles: targetRoles
            .split(",")
            .map((value) => value.trim())
            .filter(Boolean),
          max_scenarios: 5,
        }),
      });
      setForecastResult(JSON.stringify(result, null, 2));
    } catch (error) {
      setForecastResult(
        error instanceof Error ? error.message : "Forecast request failed.",
      );
    }
  }

  async function salary() {
    try {
      const params = new URLSearchParams({
        country,
        occupation,
      });
      const result = await api<Record<string, unknown>[]>(
        `/v1/career/salary?${params}`,
      );
      setSalaryResult(JSON.stringify(result, null, 2));
    } catch (error) {
      setSalaryResult(
        error instanceof Error ? error.message : "Salary lookup failed.",
      );
    }
  }

  return (
    <section>
      <h1>Career Pathways & Global Mobility</h1>
      <p>
        Pathway scenarios use verified skills and provenance-backed career data.
        They are not predictions of hiring, promotion, immigration eligibility,
        or guaranteed salary.
      </p>

      <div className="card stack">
        <label>
          Target country code
          <input value={country} onChange={(event) => setCountry(event.target.value.toUpperCase())} />
        </label>
        <label>
          Target roles, comma separated
          <input value={targetRoles} onChange={(event) => setTargetRoles(event.target.value)} />
        </label>
        <button onClick={forecast}>Build pathway scenarios</button>
      </div>

      {forecastResult && <pre>{forecastResult}</pre>}

      <div className="card stack">
        <label>
          Salary occupation title or code
          <input value={occupation} onChange={(event) => setOccupation(event.target.value)} />
        </label>
        <button onClick={salary}>Look up salary benchmarks</button>
      </div>

      {salaryResult && <pre>{salaryResult}</pre>}
    </section>
  );
}

function GovernancePanel() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [dashboard, setDashboard] = useState("");
  const [reviews, setReviews] = useState("");

  useEffect(() => {
    api<Organization[]>("/v1/organizations")
      .then((values) => {
        const governed = values.filter((organization) =>
          ["owner", "admin"].includes(organization.role),
        );
        setOrganizations(governed);
        if (governed[0]) setOrganizationId(governed[0].id);
      })
      .catch(() => undefined);
  }, []);

  async function load() {
    if (!organizationId) return;

    try {
      const [summary, queue] = await Promise.all([
        api<Record<string, unknown>>(
          `/v1/organizations/${organizationId}/compliance/dashboard`,
        ),
        api<Record<string, unknown>[]>(
          `/v1/organizations/${organizationId}/governance/reviews?limit=100`,
        ),
      ]);
      setDashboard(JSON.stringify(summary, null, 2));
      setReviews(JSON.stringify(queue, null, 2));
    } catch (error) {
      setDashboard(error instanceof Error ? error.message : "Governance load failed.");
    }
  }

  useEffect(() => {
    load();
  }, [organizationId]);

  return (
    <section>
      <h1>Governance & Compliance</h1>
      <p>
        Policy gates, evaluations, fairness review triggers, human review, and
        evidence automation. Compliance evidence is not a certification or audit opinion.
      </p>
      <select
        value={organizationId}
        onChange={(event) => setOrganizationId(event.target.value)}
      >
        {organizations.map((organization) => (
          <option value={organization.id} key={organization.id}>
            {organization.name}
          </option>
        ))}
      </select>
      <button onClick={load}>Refresh governance dashboard</button>
      <h2>Compliance dashboard</h2>
      <pre>{dashboard}</pre>
      <h2>Human review queue</h2>
      <pre>{reviews}</pre>
    </section>
  );
}


function CredentialsPanel() {
  const [credentialText, setCredentialText] = useState(
    JSON.stringify(
      {
        "@context": ["https://www.w3.org/ns/credentials/v2"],
        type: ["VerifiableCredential"],
        issuer: { id: "https://issuer.example", name: "Example Issuer" },
        credentialSubject: { id: "did:example:holder" },
      },
      null,
      2,
    ),
  );
  const [verifier, setVerifier] = useState("none");
  const [result, setResult] = useState("");
  const [credentials, setCredentials] = useState<Record<string, unknown>[]>([]);

  async function refresh() {
    try {
      setCredentials(await api<Record<string, unknown>[]>("/v1/credentials"));
    } catch (error) {
      setResult(error instanceof Error ? error.message : "Could not load credentials.");
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <section>
      <h1>Verifiable Credentials</h1>
      <p>
        Local validation checks structure and expiry. A credential is not labeled
        cryptographically verified unless the configured verifier validates its proof
        and status.
      </p>
      <div className="card stack">
        <textarea
          className="json-editor short"
          value={credentialText}
          onChange={(event) => setCredentialText(event.target.value)}
        />
        <select value={verifier} onChange={(event) => setVerifier(event.target.value)}>
          <option value="none">Structural validation only</option>
          <option value="configured_remote">Configured cryptographic verifier</option>
        </select>
        <button
          onClick={async () => {
            try {
              const value = await api<Record<string, unknown>>("/v1/credentials", {
                method: "POST",
                body: JSON.stringify({
                  credential: JSON.parse(credentialText),
                  verifier,
                }),
              });
              setResult(JSON.stringify(value, null, 2));
              await refresh();
            } catch (error) {
              setResult(error instanceof Error ? error.message : "Credential import failed.");
            }
          }}
        >
          Validate and store credential
        </button>
      </div>
      <pre>{result}</pre>
      <h2>My credentials</h2>
      <pre>{JSON.stringify(credentials, null, 2)}</pre>
    </section>
  );
}

function PortfolioPanel() {
  const [payload, setPayload] = useState(
    JSON.stringify(
      {
        headline: "",
        about: "",
        projects: [],
        links: [],
        include_verified_credentials: true,
      },
      null,
      2,
    ),
  );
  const [result, setResult] = useState("");

  useEffect(() => {
    api<Record<string, unknown>>("/v1/portfolio")
      .then((value) => {
        const portfolio = (value.portfolio ?? {}) as Record<string, unknown>;
        setPayload(
          JSON.stringify(
            {
              headline: portfolio.headline ?? "",
              about: portfolio.about ?? "",
              projects: portfolio.projects ?? [],
              links: portfolio.links ?? [],
              include_verified_credentials: true,
            },
            null,
            2,
          ),
        );
      })
      .catch(() => undefined);
  }, []);

  return (
    <section>
      <h1>Career Portfolio</h1>
      <p>
        Portfolio content is encrypted. Public sharing is revocable and expires;
        contact information is excluded unless you explicitly opt in.
      </p>
      <textarea
        className="json-editor"
        value={payload}
        onChange={(event) => setPayload(event.target.value)}
      />
      <div className="row">
        <button
          onClick={async () => {
            try {
              const value = await api<Record<string, unknown>>("/v1/portfolio", {
                method: "PUT",
                body: JSON.stringify(JSON.parse(payload)),
              });
              setResult(JSON.stringify(value, null, 2));
            } catch (error) {
              setResult(error instanceof Error ? error.message : "Portfolio update failed.");
            }
          }}
        >
          Save encrypted portfolio
        </button>
        <button
          className="secondary"
          onClick={async () => {
            try {
              const value = await api<Record<string, unknown>>("/v1/portfolio/shares", {
                method: "POST",
                body: JSON.stringify({
                  expires_in_days: 30,
                  include_contact: false,
                  include_experience: true,
                  include_education: true,
                  include_skills: true,
                  include_credentials: true,
                  include_projects: true,
                }),
              });
              setResult(JSON.stringify(value, null, 2));
            } catch (error) {
              setResult(error instanceof Error ? error.message : "Portfolio share failed.");
            }
          }}
        >
          Create 30-day public share
        </button>
      </div>
      <pre>{result}</pre>
    </section>
  );
}

function LearningAndTrendsPanel() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [connectionText, setConnectionText] = useState(
    JSON.stringify(
      {
        provider: "open_edx",
        base_url: "https://learning.example",
        credentials: { auth_type: "none" },
        enabled: true,
        metadata: {},
      },
      null,
      2,
    ),
  );
  const [query, setQuery] = useState("");
  const [catalog, setCatalog] = useState("");
  const [trendText, setTrendText] = useState(
    JSON.stringify(
      {
        source: "BLS Public Data API v2",
        country_code: "USA",
        region_code: "",
        occupation_code: "",
        metric: "employment",
      },
      null,
      2,
    ),
  );
  const [trend, setTrend] = useState("");

  useEffect(() => {
    api<Organization[]>("/v1/organizations")
      .then((values) => {
        setOrganizations(values);
        if (values[0]) setOrganizationId(values[0].id);
      })
      .catch(() => undefined);
  }, []);

  return (
    <section>
      <h1>Learning Providers & Labor Trends</h1>
      <p>
        Provider endpoints must be explicitly allowlisted. Labor trend output is a
        historical trend projection with provenance, not an employment probability.
      </p>
      <select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
        {organizations.map((organization) => (
          <option value={organization.id} key={organization.id}>
            {organization.name}
          </option>
        ))}
      </select>

      <h2>Authorized learning provider</h2>
      <textarea
        className="json-editor short"
        value={connectionText}
        onChange={(event) => setConnectionText(event.target.value)}
      />
      <button
        disabled={!organizationId}
        onClick={async () => {
          try {
            const value = await api<Record<string, unknown>>(
              `/v1/organizations/${organizationId}/learning/connections`,
              {
                method: "POST",
                body: JSON.stringify(JSON.parse(connectionText)),
              },
            );
            setCatalog(JSON.stringify(value, null, 2));
          } catch (error) {
            setCatalog(error instanceof Error ? error.message : "Learning setup failed.");
          }
        }}
      >
        Save encrypted learning connection
      </button>

      <div className="row">
        <input
          placeholder="Catalog search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
        />
        <button
          disabled={!organizationId}
          onClick={async () => {
            try {
              const params = new URLSearchParams({ q: query });
              const value = await api<Record<string, unknown>[]>(
                `/v1/organizations/${organizationId}/learning/catalog?${params}`,
              );
              setCatalog(JSON.stringify(value, null, 2));
            } catch (error) {
              setCatalog(error instanceof Error ? error.message : "Catalog search failed.");
            }
          }}
        >
          Search synced catalog
        </button>
      </div>
      <pre>{catalog}</pre>

      <h2>Labor trend projection</h2>
      <textarea
        className="json-editor short"
        value={trendText}
        onChange={(event) => setTrendText(event.target.value)}
      />
      <button
        onClick={async () => {
          try {
            const value = await api<Record<string, unknown>>("/v1/career/labor-trend", {
              method: "POST",
              body: JSON.stringify(JSON.parse(trendText)),
            });
            setTrend(JSON.stringify(value, null, 2));
          } catch (error) {
            setTrend(error instanceof Error ? error.message : "Trend request failed.");
          }
        }}
      >
        Calculate trend
      </button>
      <pre>{trend}</pre>
    </section>
  );
}

function Phase8AssurancePanel() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [inventoryText, setInventoryText] = useState(
    JSON.stringify(
      {
        system_key: "career-assistant",
        version: "1.0.0",
        name: "Career Assistant",
        owner: "AI Governance",
        intended_purpose:
          "Assist candidates and human recruiters with career preparation and job-fit analysis.",
        operator_role: "both",
        lifecycle_status: "validation",
        jurisdictions: ["US", "EU"],
        model_names: ["gpt-5.6"],
        data_categories: ["candidate_profile", "job_description"],
        employment_use: true,
        education_use: false,
        profiles_natural_persons: true,
        materially_influences_decisions: false,
        human_oversight: true,
        iso42001_in_scope: true,
      },
      null,
      2,
    ),
  );
  const [dashboard, setDashboard] = useState("");
  const [inventory, setInventory] = useState("");

  useEffect(() => {
    api<Organization[]>("/v1/organizations")
      .then((values) => {
        const governed = values.filter((item) => ["owner", "admin"].includes(item.role));
        setOrganizations(governed);
        if (governed[0]) setOrganizationId(governed[0].id);
      })
      .catch(() => undefined);
  }, []);

  async function refresh() {
    if (!organizationId) return;

    try {
      const [summary, systems] = await Promise.all([
        api<Record<string, unknown>>(
          `/v1/organizations/${organizationId}/governance/phase8/dashboard`,
        ),
        api<Record<string, unknown>[]>(
          `/v1/organizations/${organizationId}/ai-inventory`,
        ),
      ]);
      setDashboard(JSON.stringify(summary, null, 2));
      setInventory(JSON.stringify(systems, null, 2));
    } catch (error) {
      setDashboard(error instanceof Error ? error.message : "Assurance load failed.");
    }
  }

  useEffect(() => {
    refresh();
  }, [organizationId]);

  return (
    <section>
      <h1>Phase 8 AI Assurance</h1>
      <p>
        AI inventory, conservative EU AI Act classification triage, risk/incident
        workflows, ISO/IEC 42001 management-system crosswalk, and automated evidence.
        This dashboard is not a legal opinion or certification result.
      </p>
      <select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
        {organizations.map((organization) => (
          <option value={organization.id} key={organization.id}>
            {organization.name}
          </option>
        ))}
      </select>
      <textarea
        className="json-editor short"
        value={inventoryText}
        onChange={(event) => setInventoryText(event.target.value)}
      />
      <div className="row">
        <button
          disabled={!organizationId}
          onClick={async () => {
            try {
              const value = await api<Record<string, unknown>>(
                `/v1/organizations/${organizationId}/ai-inventory`,
                {
                  method: "POST",
                  body: JSON.stringify(JSON.parse(inventoryText)),
                },
              );
              setInventory(JSON.stringify(value, null, 2));
              await refresh();
            } catch (error) {
              setInventory(error instanceof Error ? error.message : "Inventory create failed.");
            }
          }}
        >
          Register AI system
        </button>
        <button
          className="secondary"
          disabled={!organizationId}
          onClick={async () => {
            const value = await api<Record<string, unknown>>(
              `/v1/organizations/${organizationId}/governance/phase8/evidence`,
              { method: "POST" },
            );
            setDashboard(JSON.stringify(value, null, 2));
            await refresh();
          }}
        >
          Collect governance evidence
        </button>
      </div>
      <h2>Assurance dashboard</h2>
      <pre>{dashboard}</pre>
      <h2>AI inventory</h2>
      <pre>{inventory}</pre>
    </section>
  );
}


function Phase9PassportPanel() {
  const [did, setDid] = useState("");
  const [result, setResult] = useState("");

  async function buildPassport() {
    try {
      const value = await api<Record<string, unknown>>("/v1/skills-passport", {
        method: "PUT",
        body: JSON.stringify({
          title: "Career Skills Passport",
          include_profile_summary: true,
          include_experience: true,
          include_education: true,
          include_verified_credentials: true,
          include_unverified_credentials: false,
          include_contact: false,
          include_portfolio: true,
        }),
      });
      setResult(JSON.stringify(value, null, 2));
    } catch (error) {
      setResult(error instanceof Error ? error.message : "Passport creation failed.");
    }
  }

  return (
    <section>
      <h1>Portable Career Record & Skills Passport</h1>
      <p>
        Register a public holder DID only. Wallet private keys stay with the
        candidate. Portable exports are marked unsigned unless backed by an actual
        cryptographic issuer proof.
      </p>

      <div className="row">
        <input
          placeholder="did:key:... or did:web:..."
          value={did}
          onChange={(event) => setDid(event.target.value)}
        />
        <button
          disabled={!did}
          onClick={async () => {
            try {
              const value = await api<Record<string, unknown>>("/v1/wallets", {
                method: "POST",
                body: JSON.stringify({
                  holder_did: did,
                  wallet_type: "external",
                  metadata: {},
                }),
              });
              setResult(JSON.stringify(value, null, 2));
            } catch (error) {
              setResult(error instanceof Error ? error.message : "Wallet registration failed.");
            }
          }}
        >
          Register holder DID
        </button>
      </div>

      <div className="row">
        <button onClick={buildPassport}>Build skills passport</button>
        <button
          className="secondary"
          onClick={async () => {
            try {
              const value = await api<Record<string, unknown>>(
                "/v1/portable-career-record",
              );
              setResult(JSON.stringify(value, null, 2));
            } catch (error) {
              setResult(error instanceof Error ? error.message : "Export failed.");
            }
          }}
        >
          Export portable career record
        </button>
      </div>
      <pre>{result}</pre>
    </section>
  );
}

function Phase9PrivacyPanel() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [requests, setRequests] = useState("");
  const [controls, setControls] = useState("");
  const [requestType, setRequestType] = useState("access");

  useEffect(() => {
    api<Organization[]>("/v1/organizations")
      .then((values) => {
        setOrganizations(values);
        if (values[0]) setOrganizationId(values[0].id);
      })
      .catch(() => undefined);
  }, []);

  async function loadRequests() {
    try {
      const value = await api<Record<string, unknown>[]>("/v1/privacy/requests");
      setRequests(JSON.stringify(value, null, 2));
    } catch (error) {
      setRequests(error instanceof Error ? error.message : "Privacy request load failed.");
    }
  }

  useEffect(() => {
    loadRequests();
  }, []);

  return (
    <section>
      <h1>Privacy, Retention & Continuous Controls</h1>
      <p>
        Candidate privacy-rights requests are tracked with due dates and encrypted
        results. Organization controls cover privacy assessments, lineage,
        retention, red-team exercises, and continuous monitoring.
      </p>

      <div className="row">
        <select value={requestType} onChange={(event) => setRequestType(event.target.value)}>
          <option value="access">Access</option>
          <option value="portability">Portability</option>
          <option value="rectification">Rectification</option>
          <option value="erasure">Erasure</option>
          <option value="restriction">Restriction</option>
          <option value="objection">Objection</option>
        </select>
        <button
          onClick={async () => {
            try {
              await api("/v1/privacy/requests", {
                method: "POST",
                body: JSON.stringify({
                  request_type: requestType,
                  details: "",
                }),
              });
              await loadRequests();
            } catch (error) {
              setRequests(error instanceof Error ? error.message : "Request failed.");
            }
          }}
        >
          Submit privacy request
        </button>
      </div>

      <pre>{requests}</pre>

      <h2>Organization continuous controls</h2>
      <select value={organizationId} onChange={(event) => setOrganizationId(event.target.value)}>
        {organizations.map((organization) => (
          <option value={organization.id} key={organization.id}>
            {organization.name}
          </option>
        ))}
      </select>
      <button
        disabled={!organizationId}
        onClick={async () => {
          try {
            const value = await api<Record<string, unknown>>(
              `/v1/organizations/${organizationId}/continuous-controls`,
              { method: "POST" },
            );
            setControls(JSON.stringify(value, null, 2));
          } catch (error) {
            setControls(error instanceof Error ? error.message : "Control scan failed.");
          }
        }}
      >
        Run continuous controls
      </button>
      <pre>{controls}</pre>
    </section>
  );
}

function AdminPanel() {
  const [overview, setOverview] = useState("");

  useEffect(() => {
    api<Record<string, unknown>>("/v1/admin/overview")
      .then((value) => setOverview(JSON.stringify(value, null, 2)))
      .catch((error) =>
        setOverview(error instanceof Error ? error.message : "Admin load failed."),
      );
  }, []);

  return (
    <section>
      <h1>Platform Administration</h1>
      <p>
        Platform-wide counts and recent audited administrative activity.
      </p>
      <pre>{overview}</pre>
    </section>
  );
}



function Phase10IdentityPanel() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [slug, setSlug] = useState("career-credentials");
  const [displayName, setDisplayName] = useState("Career Credentials");
  const [result, setResult] = useState("");

  useEffect(() => {
    api<Organization[]>("/v1/organizations")
      .then((values) => {
        setOrganizations(values);
        if (values[0]) setOrganizationId(values[0].id);
      })
      .catch(() => undefined);
  }, []);

  async function createProfile(kind: "issuers" | "verifiers") {
    if (!organizationId) return;

    try {
      const value = await api<Record<string, unknown>>(
        `/v1/phase10/${kind}`,
        {
          method: "POST",
          body: JSON.stringify({
            organization_id: organizationId,
            slug,
            display_name: displayName,
          }),
        },
      );
      setResult(JSON.stringify(value, null, 2));
    } catch (error) {
      setResult(
        error instanceof Error
          ? error.message
          : "Credential interoperability request failed.",
      );
    }
  }

  return (
    <section>
      <h1>OpenID Credential Interoperability</h1>
      <p>
        Phase 10 supports approved OpenID4VCI issuers, OpenID4VP verifiers,
        PKCE-bound wallet issuance, DCQL presentation requests, and selective
        disclosure. Issuer/verifier profiles remain inactive until platform
        approval.
      </p>

      <select
        value={organizationId}
        onChange={(event) => setOrganizationId(event.target.value)}
      >
        {organizations.map((organization) => (
          <option value={organization.id} key={organization.id}>
            {organization.name}
          </option>
        ))}
      </select>

      <div className="stack">
        <input
          value={slug}
          onChange={(event) => setSlug(event.target.value)}
          placeholder="Unique issuer/verifier slug"
        />
        <input
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
          placeholder="Display name"
        />
        <div className="row">
          <button
            disabled={!organizationId}
            onClick={() => createProfile("issuers")}
          >
            Create issuer profile
          </button>
          <button
            disabled={!organizationId}
            className="secondary"
            onClick={() => createProfile("verifiers")}
          >
            Create verifier profile
          </button>
        </div>
      </div>

      <p>
        The platform does not expose issuer private keys or fetch arbitrary
        external trust keys. External issuers must be installed as explicit
        trust anchors.
      </p>
      <pre>{result}</pre>
    </section>
  );
}

function Phase10PrivacyEngineeringPanel() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [result, setResult] = useState("");

  useEffect(() => {
    api<Organization[]>("/v1/organizations")
      .then((values) => {
        setOrganizations(values);
        if (values[0]) setOrganizationId(values[0].id);
      })
      .catch(() => undefined);
  }, []);

  async function run(path: string, options: RequestInit = {}) {
    try {
      const value = await api<Record<string, unknown>>(path, options);
      setResult(JSON.stringify(value, null, 2));
    } catch (error) {
      setResult(
        error instanceof Error ? error.message : "Privacy operation failed.",
      );
    }
  }

  return (
    <section>
      <h1>Phase 10 Privacy Engineering</h1>
      <p>
        Metadata-only data discovery, hash-addressed consent receipts,
        legal-hold-aware deletion plans, differentially private fixed-query
        analytics, and tamper-evident audit-chain verification.
      </p>

      <select
        value={organizationId}
        onChange={(event) => setOrganizationId(event.target.value)}
      >
        {organizations.map((organization) => (
          <option value={organization.id} key={organization.id}>
            {organization.name}
          </option>
        ))}
      </select>

      <div className="row">
        <button
          disabled={!organizationId}
          onClick={() =>
            run(`/v1/phase10/privacy/${organizationId}/discovery`, {
              method: "POST",
            })
          }
        >
          Run metadata discovery
        </button>

        <button
          className="secondary"
          onClick={() =>
            run("/v1/phase10/privacy/deletion/plan", {
              method: "POST",
              body: JSON.stringify({
                dsar_id: null,
                dry_run: true,
              }),
            })
          }
        >
          Preview deletion plan
        </button>

        <button
          disabled={!organizationId}
          className="secondary"
          onClick={() =>
            run(
              `/v1/phase10/audit/verify?organization_id=${encodeURIComponent(
                organizationId,
              )}`,
            )
          }
        >
          Verify audit chain
        </button>
      </div>

      <p>
        Differential-privacy releases use fixed count queries, minimum-cohort
        suppression, and a daily epsilon budget. They are privacy engineering
        controls, not a guarantee that a dataset is anonymous for every use.
      </p>

      <pre>{result}</pre>
    </section>
  );
}

export default App;


function Phase11SecurityPanel() {
  const [result, setResult] = useState("");

  async function loadReadiness() {
    try {
      const response = await api<Record<string, unknown>>(
        "/v1/phase11/security/readiness",
      );
      setResult(JSON.stringify(response, null, 2));
    } catch (error) {
      setResult(error instanceof Error ? error.message : "Request failed.");
    }
  }

  return (
    <section>
      <h1>Phase 11 Identity & Security</h1>
      <p>
        Passkeys, DID trust, Bitstring Status List, HAIP/mdoc readiness,
        hardware-backed key evidence, confidential-compute evidence, and
        post-quantum migration inventory.
      </p>
      <div className="row">
        <button onClick={loadReadiness}>Load security readiness</button>
        <button
          onClick={async () => {
            const response = await api<Record<string, unknown>[]>(
              "/v1/phase11/passkeys",
            );
            setResult(JSON.stringify(response, null, 2));
          }}
        >
          List my passkeys
        </button>
      </div>
      <p>
        Passkey registration/login uses the browser WebAuthn API; production
        clients should call the Phase 11 option endpoints and pass their
        `publicKey` values to `navigator.credentials.create/get`.
      </p>
      <pre>{result}</pre>
    </section>
  );
}


function Phase12TrustSecurityPanel() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [result, setResult] = useState("");

  useEffect(() => {
    api<Organization[]>("/v1/organizations")
      .then((values) => {
        setOrganizations(values);
        if (values[0]) setOrganizationId(values[0].id);
      })
      .catch(() => undefined);
  }, []);

  async function loadReadiness() {
    try {
      const response = await api<Record<string, unknown>>(
        "/v1/phase12/readiness",
      );
      setResult(JSON.stringify(response, null, 2));
    } catch (error) {
      setResult(error instanceof Error ? error.message : "Request failed.");
    }
  }

  async function listTrustAnchors() {
    if (!organizationId) return;

    try {
      const response = await api<Record<string, unknown>[]>(
        `/v1/phase12/federation/${organizationId}/trust-anchors`,
      );
      setResult(JSON.stringify(response, null, 2));
    } catch (error) {
      setResult(error instanceof Error ? error.message : "Request failed.");
    }
  }

  async function listRuntimeEvents() {
    if (!organizationId) return;

    try {
      const response = await api<Record<string, unknown>[]>(
        `/v1/phase12/runtime/${organizationId}/events`,
      );
      setResult(JSON.stringify(response, null, 2));
    } catch (error) {
      setResult(error instanceof Error ? error.message : "Request failed.");
    }
  }

  return (
    <section>
      <h1>Phase 12 Trust & Runtime Security</h1>
      <p>
        OpenID Federation 1.1 trust chains, wallet-attestation trust anchors,
        credential-policy negotiation, HSM signing, SPIFFE/SPIRE workload
        identity, attestation-gated inference, and bounded runtime containment.
      </p>

      <select
        value={organizationId}
        onChange={(event) => setOrganizationId(event.target.value)}
      >
        {organizations.map((organization) => (
          <option value={organization.id} key={organization.id}>
            {organization.name}
          </option>
        ))}
      </select>

      <div className="row">
        <button onClick={loadReadiness}>Load Phase 12 readiness</button>
        <button
          className="secondary"
          disabled={!organizationId}
          onClick={listTrustAnchors}
        >
          Federation trust anchors
        </button>
        <button
          className="secondary"
          disabled={!organizationId}
          onClick={listRuntimeEvents}
        >
          Runtime security events
        </button>
      </div>

      <p>
        Private HSM keys and workload SVID private keys are not stored in this
        application. Automated containment is limited to pre-approved,
        reversible application controls; infrastructure isolation remains
        subject to an authorized security controller.
      </p>

      <pre>{result}</pre>
    </section>
  );
}

function Phase13TrustAISecurityPanel() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [scanText, setScanText] = useState(
    "This role requires Python, SQL, and stakeholder communication.",
  );
  const [result, setResult] = useState("");

  useEffect(() => {
    api<Organization[]>("/v1/organizations")
      .then((values) => {
        setOrganizations(values);
        if (values[0]) setOrganizationId(values[0].id);
      })
      .catch(() => undefined);
  }, []);

  async function call(path: string) {
    try {
      const response = await api<Record<string, unknown>>(path);
      setResult(JSON.stringify(response, null, 2));
    } catch (error) {
      setResult(error instanceof Error ? error.message : "Request failed.");
    }
  }

  async function scanPrompt() {
    try {
      const response = await api<Record<string, unknown>>(
        "/v1/phase13/prompt-injection/scan",
        {
          method: "POST",
          body: JSON.stringify({
            organization_id: organizationId || null,
            source_type: "dashboard",
            source_id: "manual-scan",
            content: scanText,
          }),
        },
      );
      setResult(JSON.stringify(response, null, 2));
    } catch (error) {
      setResult(error instanceof Error ? error.message : "Request failed.");
    }
  }

  return (
    <section>
      <h1>Phase 13 Multi-Region Trust & AI Security</h1>
      <p>
        Multi-region trust continuity, cross-cloud workload identity,
        transparency logs, signed model releases, confidential RAG, and
        permission-manifest enforcement for agent actions.
      </p>

      <select
        value={organizationId}
        onChange={(event) => setOrganizationId(event.target.value)}
      >
        {organizations.map((organization) => (
          <option value={organization.id} key={organization.id}>
            {organization.name}
          </option>
        ))}
      </select>

      <div className="row">
        <button onClick={() => call("/v1/phase13/readiness")}>
          Load Phase 13 readiness
        </button>
        <button
          className="secondary"
          disabled={!organizationId}
          onClick={() =>
            call(
              `/v1/phase13/transparency/verify?organization_id=${encodeURIComponent(
                organizationId,
              )}&log_name=career-trust`,
            )
          }
        >
          Verify transparency log
        </button>
      </div>

      <h2>Untrusted-content scan</h2>
      <textarea
        value={scanText}
        onChange={(event) => setScanText(event.target.value)}
      />
      <button disabled={!scanText.trim()} onClick={scanPrompt}>
        Scan content
      </button>

      <p>
        The scanner is only one defense. Phase 13 also disables model tools in
        the gateway, separates untrusted retrieval context, requires signed
        model releases where configured, and checks every agent action against
        an explicit permission manifest.
      </p>

      <pre>{result}</pre>
    </section>
  );
}


function Phase14AgentsOperationsPanel() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [approvalId, setApprovalId] = useState("");
  const [decision, setDecision] = useState<"approve" | "reject">("reject");
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);
  const [reviewedReference, setReviewedReference] = useState("");
  const [approvalDetails, setApprovalDetails] = useState("");

  useEffect(() => {
    api<Organization[]>("/v1/organizations")
      .then((values) => {
        setOrganizations(values);
        if (values[0]) setOrganizationId(values[0].id);
      })
      .catch(() => undefined);
  }, []);

  async function loadReadiness() {
    try {
      const response = await api<Record<string, unknown>>("/v1/phase14/readiness");
      setResult(JSON.stringify(response, null, 2));
    } catch (error) {
      setResult(error instanceof Error ? error.message : "Readiness request failed.");
    }
  }

  async function review(event: FormEvent) {
    event.preventDefault();
    if (!organizationId || !approvalId.trim() ||
        reviewedReference !== `${organizationId}:${approvalId.trim()}`) return;
    setBusy(true);
    try {
      const response = await api<Record<string, unknown>>(
        `/v1/phase14/approvals/${encodeURIComponent(approvalId.trim())}/review`,
        { method: "POST", body: JSON.stringify({ organization_id: organizationId, decision }) }
      );
      setResult(JSON.stringify(response, null, 2));
      setApprovalId("");
      setApprovalDetails("");
      setReviewedReference("");
    } catch (error) {
      setResult(error instanceof Error ? error.message : "Approval review failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h1>Phase 14 Agent Trust & Multi-Region Operations</h1>
      <p>
        Explicit Ed25519 capability grants, default-deny Phase 13 agent manifests,
        agent-isolated encrypted memory, auditable human checkpoints, and SLO-based
        multi-region readiness.
      </p>
      <div className="row">
        <button onClick={loadReadiness}>Load Phase 14 readiness</button>
      </div>
      <h2>Human approval checkpoint</h2>
      <p>
        Review only a pre-existing checkpoint after independently verifying its
        intent and payload digest in an authorized audit channel. This action
        requires organization owner/admin authorization. Rejected requests
        cannot be replayed as approved.
      </p>
      <form onSubmit={review} className="stack">
        <label>
          Organization
          <select
            value={organizationId}
            onChange={(event) => {
              setOrganizationId(event.target.value);
              setReviewedReference("");
              setApprovalDetails("");
            }}
          >
            {organizations.map((organization) => (
              <option value={organization.id} key={organization.id}>
                {organization.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Approval reference
          <input
            value={approvalId}
            onChange={(event) => {
              setApprovalId(event.target.value);
              setReviewedReference("");
              setApprovalDetails("");
            }}
            placeholder="Approval ID from trusted workflow"
          />
        </label>
        <button
          className="secondary"
          type="button"
          disabled={!organizationId || !approvalId.trim() || busy}
          onClick={async () => {
            setReviewedReference("");
            setApprovalDetails("");
            try {
              const value = await api<Record<string, unknown>>(
                `/v1/phase14/approvals/${encodeURIComponent(approvalId.trim())}?organization_id=${encodeURIComponent(organizationId)}`
              );
              setApprovalDetails(JSON.stringify(value, null, 2));
              if (value.state === "pending") {
                setReviewedReference(`${organizationId}:${approvalId.trim()}`);
              }
            } catch (error) {
              setResult(error instanceof Error ? error.message : "Could not load checkpoint.");
            }
          }}
        >
          Inspect checkpoint and payload digest
        </button>
        <pre>{approvalDetails}</pre>
        <label>
          Review decision
          <select
            value={decision}
            onChange={(event) => setDecision(event.target.value as "approve" | "reject")}
          >
            <option value="reject">Reject</option>
            <option value="approve">Approve</option>
          </select>
        </label>
        <button type="submit" disabled={!organizationId || !approvalId.trim() || busy ||
          reviewedReference !== `${organizationId}:${approvalId.trim()}`}>
          {busy ? "Submitting..." : "Record review"}
        </button>
      </form>
      <pre>{result}</pre>
      <p>
        Signing keys, private agent memory and bearer capability tokens are
        intentionally not exposed in the dashboard. Production failover and chaos
        exercises remain operationally gated outside this UI.
      </p>
    </section>
  );
}


/** Authenticated B-track workspace: no secrets saved to browser storage. */
function Phase1517StudioPanel() {
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [org, setOrg] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [summary, setSummary] = useState("");
  const [requirements, setRequirements] = useState("");
  const [evidence, setEvidence] = useState("");
  const [template, setTemplate] = useState<"general" | "federal" | "technical">("general");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState("");
  const [draft, setDraft] = useState("");
  const [draftHtml, setDraftHtml] = useState("");
  const [regionInput, setRegionInput] = useState("region-a:healthy\nregion-b:unknown");
  const [primaryRegion, setPrimaryRegion] = useState("region-a");
  const [lastAction, setLastAction] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api<Organization[]>("/v1/organizations").then((values) => {
      setOrgs(values);
      if (values[0]) setOrg(values[0].id);
    }).catch(() => setResult("Organization list unavailable."));
  }, []);
  async function send(path: string, payload: Record<string, unknown>) {
    setBusy(true);
    try {
      const response = await api<Record<string, unknown>>(path, { method: "POST", body: JSON.stringify({organization_id: org, ...payload}) });
      setLastAction(path);
      setResult(JSON.stringify(response, null, 2));
      if (typeof response.resume_text === "string") {
        setDraft(response.resume_text);
        setDraftHtml(typeof response.resume_html === "string" ? response.resume_html : "");
      }
    } catch (error) {
      setResult(error instanceof Error ? error.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  }
  function exportDraft(content: string, mime: string, extension: string) {
    if (!content) return;
    const blob = new Blob([content], {type: mime});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `career-resume-draft.${extension}`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 3000);
  }
  const selectedOrg = orgs.find((o) => o.id === org);
  const canManageOperations = selectedOrg?.role === "owner" || selectedOrg?.role === "admin";
  const regionList = regionInput.split("\n").map((line) => {
    const [region_id, reported_health] = line.trim().split(":");
    return {region_id, reported_health};
  }).filter((r) => r.region_id && ["healthy", "degraded", "unavailable", "unknown"].includes(r.reported_health));
  const requirementsList = requirements.split("\n").map((v) => v.trim()).filter(Boolean);
  const evidenceList = evidence.split("\n").map((v, i) => ({id: `item_${i + 1}`, description: v.trim()})).filter((v) => v.description.length >= 8);
  return (
    <section className="studio">
      <div className="studio-hero">
        <p className="eyebrow">CAREER INTELLIGENCE WORKSPACE</p>
        <h1>Career Studio</h1>
        <p>Develop documented resumes, practice interview responses, and review deployment readiness — with human verification at every step.</p>
        <div className="studio-tags"><span>Phase 15 · Resume</span><span>Phase 16 · Interview</span><span>Phase 17 · Operations</span></div>
      </div>
      <div className="studio-workspace">
        <label>Active organization
          <select value={org} onChange={(event) => {setOrg(event.target.value);setResult("");}}>
            {orgs.map((o) => <option key={o.id} value={o.id}>{o.name} · {o.role}</option>)}
          </select>
        </label>
        {!org && <p className="error" role="alert">An organization is required. Refresh after creating an account or organization.</p>}
        <div className="studio-section">
          <div className="studio-section-head"><span className="studio-number">01</span><div><h2>Evidence-based resume builder</h2><p>Ground every statement in work you can substantiate.</p></div></div>
          <div className="studio-fields">
            <label>Candidate name<input value={name} onChange={(e) => setName(e.target.value)} maxLength={160} placeholder="Name as shown on application" /></label>
            <label>Target position<input value={role} onChange={(e) => setRole(e.target.value)} maxLength={160} placeholder="e.g., Cybersecurity Analyst" /></label>
            <label className="full">Verified professional summary<textarea value={summary} onChange={(e) => setSummary(e.target.value)} maxLength={2000} placeholder="Use verified responsibilities, outcomes, and qualifications." /></label>
            <label className="full">Target job requirements — one per line<textarea value={requirements} onChange={(e) => setRequirements(e.target.value)} placeholder="List the qualifications from the vacancy announcement." /></label>
            <label className="full">Documented experience — one statement per line<textarea value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="Include only work you can verify." /></label>
            <label>Resume format<select value={template} onChange={(e) => setTemplate(e.target.value as typeof template)}><option value="general">Professional</option><option value="federal">Federal application checklist</option><option value="technical">Technical</option></select></label>
          </div>
          <div className="studio-actions">
            <button disabled={!org || busy || name.trim().length < 2 || role.trim().length < 3 || summary.trim().length < 10 || !requirementsList.length || requirementsList.length > 30 || evidenceList.length > 100} onClick={() => send("/v1/phase15/resume/draft", {candidate_name:name,target_role:role,summary,requirements:requirementsList,evidence:evidenceList,template})}>{busy ? "Working…" : "Generate evidence-based draft"}</button>
            <button className="secondary" disabled={!org || busy || !requirementsList.length} onClick={() => send("/v1/phase15/resume/evidence-map", {requirements: requirementsList, evidence: evidenceList})}>Review qualification gaps</button>
            <button className="secondary" disabled={!draft} onClick={() => exportDraft(draft, "text/plain;charset=utf-8", "txt")}>Export TXT</button>
            <button className="secondary" disabled={!draftHtml} onClick={() => exportDraft(draftHtml, "text/html;charset=utf-8", "html")}>Export HTML / print PDF</button>
          </div>
          {draft && <details className="studio-preview"><summary>Review resume draft</summary><pre>{draft}</pre></details>}
          <p className="studio-note">Federal mode is a completeness prompt, not an official USAJOBS-format compliance check. All claims require your review.</p>
        </div>
        <div className="studio-section">
          <div className="studio-section-head"><span className="studio-number">02</span><div><h2>Interview preparation</h2><p>Practice a real question and receive explainable feedback.</p></div></div>
          <label>Interview question<input value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={1000} placeholder="Describe a time you resolved competing priorities." /></label>
          <label>Your answer<textarea value={answer} onChange={(e) => setAnswer(e.target.value)} maxLength={12000} placeholder="Situation, task, your actions, verified outcome, and lesson learned." /></label>
          <div className="studio-actions">
            <button disabled={!org || busy || question.trim().length < 10 || answer.trim().length < 20} onClick={() => send("/v1/phase16/interview/simulate", {question,answer,competency:role || "professional experience"})}>Score practice answer</button>
            <button className="secondary" disabled={!org || busy || !requirementsList.length} onClick={() => send("/v1/phase16/interview/plan", {requirements:requirementsList,evidence:evidenceList})}>Generate practice questions</button>
          </div>
          <p className="studio-note">Practice scores are keyword-based feedback, not independently verified evaluations or predictions of hiring outcomes.</p>
        </div>
        <div className="studio-section">
          <div className="studio-section-head"><span className="studio-number">03</span><div><h2>Multi-region operational readiness</h2><p>Read-only planning; no traffic changes or autonomous failover.</p></div></div>
          {canManageOperations ? <>
            <label>Region inventory (region-id:health, one per line)<textarea value={regionInput} onChange={(e) => setRegionInput(e.target.value)} placeholder="region-a:healthy" /></label>
            <label>Proposed primary<input value={primaryRegion} onChange={(e) => setPrimaryRegion(e.target.value)} maxLength={100} /></label>
            <button className="secondary" disabled={!org || busy || regionList.length === 0 || regionList.length > 12} onClick={() => send("/v1/phase17/operations/plan", {regions:regionList,desired_primary:primaryRegion || null, attestations:[]})}>Generate read-only failover plan</button>
            <p className="studio-note">Operator reports are unverified. The API will retain missing checks and failover blockers until independently validated.</p>
          </> : <p className="studio-note">Owner or admin organization access is required to review operational plans.</p>}
        </div>
        {result && <section className="studio-output" aria-live="polite"><h2>Result {lastAction && <small>· {lastAction.split("/").slice(-2).join(" / ")}</small>}</h2><pre>{result}</pre></section>}
      </div>
    </section>
  );
}
