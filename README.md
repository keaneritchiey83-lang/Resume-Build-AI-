# Resume-Build-AI 🤖📄

An intelligent AI-driven resume and interview preparation platform designed for modern professionals targeting both private sector and federal government roles.

Built for precision. Optimized for hiring systems. Designed for results.

## 🚀 Quick Start

### Prerequisites

- Node.js 20+ and npm
- PostgreSQL 16+ (or use Docker)
- OpenAI API key

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/keaneritchiey83-lang/Resume-Build-AI-.git
cd Resume-Build-AI-
```

2. **Set up environment variables**
```bash
# Root directory
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Backend
cp backend/.env.example backend/.env
# Edit backend/.env with your configuration

# Frontend
cp frontend/.env.example frontend/.env
```

3. **Install dependencies**
```bash
# Backend
cd backend
npm install

# Frontend
cd ../frontend
npm install --legacy-peer-deps
```

4. **Set up the database**
```bash
# Create PostgreSQL database
createdb resume_build_ai

# The schema will be created automatically on first run
```

5. **Run the application**

**Development mode:**
```bash
# Terminal 1 - Backend
cd backend
npm run dev

# Terminal 2 - Frontend
cd frontend
npm run dev
```

**Using Docker:**
```bash
# From root directory
docker-compose up
```

The application will be available at:
- Frontend: http://localhost:5173 (dev) or http://localhost (Docker)
- Backend API: http://localhost:3000
- Database: localhost:5432

## 🧪 Testing

### Backend Tests
```bash
cd backend
npm test           # Run all tests with coverage
npm run test:watch # Watch mode
npm run lint       # Run ESLint
```

### Frontend Tests
```bash
cd frontend
npm test           # Run all tests with coverage
npm run test:watch # Watch mode
npm run lint       # Run ESLint
```

### Run All Tests
```bash
# From root directory
cd backend && npm test && cd ../frontend && npm test
```

## 🏗️ Project Structure

```
Resume-Build-AI-/
├── backend/                 # Node.js + Express backend
│   ├── src/
│   │   ├── routes/         # API route definitions
│   │   ├── controllers/    # Request handlers
│   │   ├── services/       # Business logic (AI integration)
│   │   ├── middleware/     # Express middleware
│   │   ├── models/         # Database models
│   │   ├── config/         # Configuration files
│   │   └── server.js       # Entry point
│   ├── tests/              # Backend unit tests
│   └── Dockerfile
├── frontend/               # React + Vite frontend
│   ├── src/
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   ├── services/      # API client
│   │   ├── utils/         # Utility functions
│   │   └── test/          # Frontend tests
│   ├── Dockerfile
│   └── nginx.conf
├── .github/workflows/     # CI/CD configuration
├── docker-compose.yml     # Docker orchestration
└── README.md
```

## 🔧 Technology Stack

### Frontend
- **React 19** - UI framework
- **Vite** - Build tool
- **React Router** - Routing
- **jsPDF 4.1.0** - PDF generation (security-patched version)
- **Axios** - HTTP client
- **Vitest** - Testing framework
- **React Testing Library** - Component testing

### Backend
- **Node.js 20** - Runtime environment
- **Express** - Web framework
- **OpenAI API** - AI integration
- **PostgreSQL** - Database
- **Winston** - Logging
- **Helmet** - Security middleware
- **Express Rate Limit** - Rate limiting
- **Jest** - Testing framework
- **Supertest** - API testing

### DevOps
- **Docker** - Containerization
- **Docker Compose** - Multi-container orchestration
- **GitHub Actions** - CI/CD
- **ESLint** - Code linting
- **Nginx** - Frontend web server

## 🚀 Core Capabilities
1️⃣ Advanced Resume Generation Engine
✔ ATS Optimization Layer

Keyword extraction from job postings

Semantic alignment with required competencies

Automated skills clustering

Industry-specific terminology calibration

Formatting compliant with parsing engines (Workday, Taleo, USAJOBS, Greenhouse)

✔ Achievement Quantification Engine

Converts generic tasks into impact-driven statements

Inserts measurable metrics (cost savings, uptime %, revenue impact, productivity gains)

STAR-to-bullet transformation logic

Leadership and strategic framing enhancements

✔ Intelligent Role Mapping

Maps job requirements to:

Past experience

Certifications

Education

Projects

Identifies skill gaps

Suggests targeted language improvements

📄 2-Page Resume Frameworks

Resume-Build-AI generates structured, optimized two-page professional resumes tailored to sector standards.

🏢 Private Sector Resume (2-Page Format)

Page 1

Executive Summary (3–5 impact-driven lines)

Core Competencies (keyword-dense)

Technical Skills Matrix

Professional Experience (Recent roles with quantified results)

Page 2

Continued Experience

Projects (AI, DevOps, Cyber, etc.)

Certifications

Education

Leadership / Publications (Optional)

Optimized For:

ATS scanning

Recruiter 6-second review

Hiring manager clarity

Metrics-first storytelling

🏛 Federal Resume (USAJOBS-Compliant, 2+ Pages Structured for Federal Standards)

Federal resumes differ significantly from private-sector resumes. Resume-Build-AI includes:

Hours worked per week

Supervisor contact permissions

Salary information

Detailed duty narratives

Knowledge, Skills, and Abilities (KSAs)

Executive Order alignment capability

Specialized experience mapping to GS-level criteria

Federal Resume Structure

Page 1

Detailed Professional Summary

Core Competencies (aligned to vacancy announcement)

Federal Keywords (e.g., DoD frameworks, RMF, NIST)

Page 2

Expanded duty descriptions

Process improvement metrics

Compliance documentation

Security clearance details

Technical systems used

Optimized for:

GS-07 through GS-15 scoring

Specialized experience qualification

Questionnaire alignment

HR screening compliance

🎯 Interview Preparation Intelligence Module

Resume-Build-AI extends beyond documents and prepares candidates for structured interviews.

🧠 Behavioral Interview Preparation

Generates customized answers using:

STAR method

Federal CCAR method

Leadership competency models

Technical scenario modeling

Sample Behavioral Categories:

Conflict resolution

Risk mitigation

Leadership under pressure

Process improvement

Compliance & governance

Ethical decision-making

💻 Technical Interview Preparation

Based on job description analysis, system generates:

Likely technical questions

Scenario-based challenges

Cybersecurity case simulations

Architecture whiteboard prompts

DevOps troubleshooting scenarios

Policy interpretation questions (for federal roles)

🏛 Federal Panel Interview Preparation

Includes:

Structured performance-based questions

Executive Order alignment discussions

Regulatory compliance scenarios

Mission alignment storytelling

Chain-of-command communication examples

📊 Career Strategy Engine

Resume-Build-AI also provides:

Job market keyword heat mapping

Skill gap identification

Certification recommendations

Role trajectory mapping

Salary benchmarking insights

LinkedIn profile optimization guidance

Application tracking dashboard

🔐 Built for Security & Compliance

SOC 2 roadmap ready

Data encryption at rest and in transit

Secure API architecture

Minimal data retention model

Role-based access control (RBAC)

Secure containerized deployments

🧩 Technical Architecture Overview

Frontend: React

Backend: Node.js + Express

AI Engine: OpenAI + NLP pipeline

Data Layer: PostgreSQL

Containerization: Docker

Cloud Deployment: AWS / Vercel

Analytics: Secure usage telemetry

CI/CD: GitHub Actions

💼 Who This Is For

Cybersecurity professionals

Federal applicants (DoD, DHS, USAF, etc.)

Engineers & Developers

Program Managers

Transitioning Military Members

Mid-level to Executive professionals

🔥 What Makes Resume-Build-AI Different

Most resume builders format text.

Resume-Build-AI:

Thinks strategically.

Aligns with hiring algorithms.

Simulates recruiter psychology.

Prepares you for interviews.

Optimizes for both federal and private systems.

It transforms applicants into competitive candidates.

📦 Future Expansion

AI-powered mock interview simulator

Voice-based interview practice

Resume scoring engine

Direct LinkedIn & USAJOBS integration

Employer-side AI recruiter tool

🎯 Mission

To eliminate guesswork from job applications and equip professionals with intelligent, precision-engineered career tools.

## 📡 API Endpoints

### Resume API
- `POST /api/resume/generate` - Generate a new resume
  ```json
  {
    "jobDescription": "Software Engineer position...",
    "experience": [{"description": "Led development..."}],
    "resumeType": "private" // or "federal"
  }
  ```

- `POST /api/resume/optimize` - Optimize resume for ATS
  ```json
  {
    "resumeContent": "Resume text...",
    "jobDescription": "Job requirements..."
  }
  ```

### Interview API
- `POST /api/interview/prepare` - Generate interview questions
  ```json
  {
    "jobDescription": "Job requirements...",
    "interviewType": "behavioral" // or "technical", "federal"
  }
  ```

### Career API
- `POST /api/career/skills-gap` - Analyze skill gaps
  ```json
  {
    "currentSkills": ["JavaScript", "React"],
    "jobDescription": "Job requirements..."
  }
  ```

### Health API
- `GET /api/health` - Health check endpoint

## 🛡️ Security Features

- **Helmet.js** - Security headers
- **Rate Limiting** - API request throttling
- **Input Validation** - Request sanitization
- **Error Handling** - Secure error responses
- **Environment Variables** - Secrets management
- **CORS** - Cross-origin resource sharing configuration

## 🔄 CI/CD Pipeline

The project includes a GitHub Actions workflow that:
- Runs linting on backend and frontend
- Executes all unit tests
- Builds Docker images
- Validates the build process

## 📝 Development Guidelines

### Code Style
- Use ESLint for code quality
- Follow Airbnb JavaScript style guide (backend)
- Follow React best practices (frontend)
- Write meaningful commit messages

### Testing
- Write unit tests for new features
- Maintain test coverage above 70%
- Test both success and error cases
- Mock external dependencies

### Git Workflow
- Create feature branches from `main`
- Write descriptive commit messages
- Create pull requests for review
- Ensure CI passes before merging

## 🐳 Docker Deployment

### Build and Run
```bash
docker-compose up --build
```

### Stop Services
```bash
docker-compose down
```

### View Logs
```bash
docker-compose logs -f [service-name]
```

### Rebuild Specific Service
```bash
docker-compose up --build [service-name]
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Write/update tests
5. Ensure all tests pass
6. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 👤 Author

Richard Keane

---

Built with ❤️ for professionals seeking career advancement
