# AI-Powered Resume Builder SaaS Platform

A production-ready, full-stack Resume Builder platform with AI-powered ATS optimization, predictive callback analysis, and enterprise team features.

## 🚀 Features

### Core Features
- **AI-Powered ATS Scoring Engine**
  - Keyword matching and semantic similarity analysis
  - Impact detection for bullet points
  - Real-time optimization suggestions
  
- **Predictive Callback Model**
  - ML-based prediction of callback likelihood
  - Confidence scoring with detailed factors
  - Experience relevance analysis

- **Professional Resume Builder**
  - Modern, ATS-friendly templates
  - Real-time preview
  - PDF export functionality
  - Multi-resume management

### Authentication & Authorization
- JWT-based authentication
- Role-based access control (USER, ADMIN, TEAM_ADMIN)
- Secure password hashing with bcrypt
- Protected routes on frontend and backend

### Subscription Management
- Stripe integration for payments
- Three-tier pricing: Free, Pro, Enterprise
- Webhook handling for subscription lifecycle
- Automatic tier management

### Enterprise Features
- Team collaboration
- Member management with role control
- Team analytics dashboard
- Up to 50 members per team

### Admin Dashboard
- User management
- Subscription analytics
- System monitoring
- Revenue tracking

## 🛠 Tech Stack

### Frontend
- **Framework:** React 18 with TypeScript
- **Build Tool:** Vite
- **Routing:** React Router v6
- **State Management:** Zustand
- **Styling:** Tailwind CSS
- **HTTP Client:** Axios
- **Icons:** Lucide React

### Backend
- **Runtime:** Node.js 18+
- **Framework:** Express.js with TypeScript
- **Database:** PostgreSQL
- **ORM:** Prisma
- **Authentication:** JWT (jsonwebtoken)
- **Payment:** Stripe SDK
- **NLP:** Natural (for ATS analysis)

### Infrastructure
- **Containerization:** Docker & Docker Compose
- **CI/CD:** GitHub Actions
- **Web Server:** Nginx (for frontend)

## 📋 Prerequisites

- Node.js 18+ and npm
- PostgreSQL 15+
- Docker and Docker Compose (optional)
- Stripe account (for payments)

## 🏃 Getting Started

### Option 1: Using Docker (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/keaneritchiey83-lang/Resume-Build-AI-.git
   cd Resume-Build-AI-
   ```

2. **Set up environment variables**
   ```bash
   # Backend
   cp backend/.env.example backend/.env
   # Edit backend/.env with your configuration
   ```

3. **Start services with Docker Compose**
   ```bash
   docker-compose up --build
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:5000
   - Health check: http://localhost:5000/health

### Option 2: Local Development

#### Backend Setup

1. **Navigate to backend directory**
   ```bash
   cd backend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Set up database**
   ```bash
   # Generate Prisma client
   npm run prisma:generate
   
   # Run migrations
   npm run prisma:migrate
   ```

5. **Start development server**
   ```bash
   npm run dev
   ```

#### Frontend Setup

1. **Navigate to frontend directory**
   ```bash
   cd frontend
   ```

2. **Install dependencies**
   ```bash
   npm install
   ```

3. **Start development server**
   ```bash
   npm run dev
   ```

## 🔧 Configuration

### Backend Environment Variables

```env
# Server
NODE_ENV=development
PORT=5000

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/resumebuilder

# JWT
JWT_SECRET=your-secret-key
JWT_EXPIRES_IN=7d

# Stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID_PRO=price_...
STRIPE_PRICE_ID_ENTERPRISE=price_...

# CORS
CORS_ORIGIN=http://localhost:3000
```

### Frontend Environment Variables

Create a `.env` file in the frontend directory:

```env
VITE_API_URL=http://localhost:5000
```

## 📚 API Documentation

### Authentication Endpoints

- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `GET /api/auth/profile` - Get user profile (authenticated)

### Resume Endpoints

- `POST /api/resumes` - Create resume
- `GET /api/resumes` - Get all user resumes
- `GET /api/resumes/:id` - Get specific resume
- `PUT /api/resumes/:id` - Update resume
- `DELETE /api/resumes/:id` - Delete resume

### ATS Analysis Endpoints

- `POST /api/ats/analyze` - Analyze resume against job description
- `GET /api/ats/score/:resumeId` - Get ATS score history

### Prediction Endpoints

- `POST /api/predictions/callback` - Predict callback likelihood

### Subscription Endpoints

- `POST /api/subscriptions/checkout` - Create Stripe checkout session
- `GET /api/subscriptions` - Get user subscription
- `POST /api/subscriptions/cancel` - Cancel subscription

### Team Endpoints (Enterprise)

- `POST /api/teams` - Create team
- `GET /api/teams` - Get user teams
- `GET /api/teams/:id` - Get team details
- `POST /api/teams/:id/members` - Add team member
- `DELETE /api/teams/:id/members/:userId` - Remove member

### Admin Endpoints

- `GET /api/admin/stats` - Get dashboard statistics
- `GET /api/admin/users` - Get all users
- `GET /api/admin/subscriptions` - Get all subscriptions

## 🗄 Database Schema

The application uses Prisma ORM with the following models:

- **User** - User accounts with authentication
- **Subscription** - Subscription tier and status
- **Resume** - Resume data and metadata
- **ATSAnalysis** - ATS scoring history
- **Team** - Team/organization information
- **TeamMember** - Team membership relationships
- **CallbackPrediction** - Prediction history

## 🧪 Testing

### Backend Tests

```bash
cd backend
npm test
```

### Frontend Tests

```bash
cd frontend
npm test
```

## 🚢 Deployment

### Using Docker

Build production images:

```bash
docker-compose -f docker-compose.yml build
docker-compose -f docker-compose.yml up -d
```

### Manual Deployment

1. Build backend:
   ```bash
   cd backend
   npm run build
   npm start
   ```

2. Build frontend:
   ```bash
   cd frontend
   npm run build
   ```

Deploy the `dist` folder to your web server or CDN.

## 📊 Architecture

```
Resume-Build-AI-/
├── backend/                  # Node.js/Express backend
│   ├── src/
│   │   ├── controllers/     # Request handlers
│   │   ├── routes/          # API routes
│   │   ├── middleware/      # Auth, error handling
│   │   ├── services/        # Business logic (ATS, predictions)
│   │   └── index.ts         # App entry point
│   ├── prisma/
│   │   └── schema.prisma    # Database schema
│   └── package.json
│
├── frontend/                 # React/TypeScript frontend
│   ├── src/
│   │   ├── components/      # Reusable components
│   │   ├── pages/           # Page components
│   │   ├── services/        # API client
│   │   ├── store/           # State management
│   │   ├── types/           # TypeScript types
│   │   └── App.tsx          # Main app component
│   └── package.json
│
├── docker-compose.yml        # Docker orchestration
└── .github/workflows/        # CI/CD pipelines
```

## 🤝 Contributing

This is an open-source project. Contributions are welcome!

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔐 Security

- All passwords are hashed using bcrypt
- JWT tokens for authentication
- CORS protection
- SQL injection prevention via Prisma ORM
- Input validation on all endpoints
- Secure Stripe webhook verification

## 🐛 Known Issues & Limitations

- PDF export requires additional implementation
- Admin dashboard UI is placeholder
- Team features UI is basic
- No email notifications yet
- ATS scoring is rule-based (can be enhanced with ML models)

## 📞 Support

For support, please open an issue in the GitHub repository.

## 🙏 Acknowledgments

- Natural.js for NLP capabilities
- Stripe for payment processing
- Prisma for database management
- All open-source contributors

---

Built with ❤️ for job seekers everywhere
