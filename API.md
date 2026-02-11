# API Documentation

Base URL: `http://localhost:5000/api`

## Authentication

All authenticated endpoints require a JWT token in the Authorization header:
```
Authorization: Bearer <token>
```

## Endpoints

### Authentication

#### Register
```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123",
  "firstName": "John",
  "lastName": "Doe"
}

Response: 201
{
  "success": true,
  "data": {
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "firstName": "John",
      "lastName": "Doe",
      "role": "USER",
      "subscription": { ... }
    },
    "token": "jwt.token.here"
  }
}
```

#### Login
```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password123"
}

Response: 200
{
  "success": true,
  "data": {
    "user": { ... },
    "token": "jwt.token.here"
  }
}
```

#### Get Profile
```http
GET /auth/profile
Authorization: Bearer <token>

Response: 200
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "user@example.com",
    "firstName": "John",
    "lastName": "Doe",
    "role": "USER",
    "subscription": { ... }
  }
}
```

### Resumes

#### Create Resume
```http
POST /resumes
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Software Engineer Resume",
  "template": "modern",
  "content": {
    "personalInfo": {
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "+1234567890"
    },
    "summary": "Experienced software engineer...",
    "experience": [],
    "education": [],
    "skills": ["JavaScript", "React", "Node.js"]
  }
}

Response: 201
{
  "success": true,
  "data": {
    "id": "uuid",
    "userId": "user-uuid",
    "title": "Software Engineer Resume",
    ...
  }
}
```

#### Get All Resumes
```http
GET /resumes
Authorization: Bearer <token>

Response: 200
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "title": "Software Engineer Resume",
      "atsScore": 0.85,
      "updatedAt": "2024-01-01T00:00:00Z",
      ...
    }
  ]
}
```

#### Get Resume by ID
```http
GET /resumes/:id
Authorization: Bearer <token>

Response: 200
{
  "success": true,
  "data": {
    "id": "uuid",
    "title": "Software Engineer Resume",
    "content": { ... },
    "atsAnalyses": [ ... ]
  }
}
```

#### Update Resume
```http
PUT /resumes/:id
Authorization: Bearer <token>
Content-Type: application/json

{
  "title": "Updated Title",
  "content": { ... }
}

Response: 200
{
  "success": true,
  "data": { ... }
}
```

#### Delete Resume
```http
DELETE /resumes/:id
Authorization: Bearer <token>

Response: 200
{
  "success": true,
  "message": "Resume deleted successfully"
}
```

### ATS Analysis

#### Analyze Resume
```http
POST /ats/analyze
Authorization: Bearer <token>
Content-Type: application/json

{
  "resumeId": "resume-uuid",
  "jobDescription": "We are looking for a software engineer with experience in React..."
}

Response: 200
{
  "success": true,
  "data": {
    "overallScore": 0.78,
    "keywordScore": 0.75,
    "semanticScore": 0.82,
    "impactScore": 0.76,
    "suggestions": [
      "Include more relevant keywords...",
      "Add quantifiable achievements..."
    ],
    "matchedKeywords": ["react", "javascript", "software"],
    "missingKeywords": ["typescript", "testing", "agile"],
    "analysisId": "uuid"
  }
}
```

#### Get ATS Score
```http
GET /ats/score/:resumeId
Authorization: Bearer <token>

Response: 200
{
  "success": true,
  "data": {
    "id": "uuid",
    "atsScore": 0.85,
    "atsAnalyses": [
      {
        "id": "uuid",
        "overallScore": 0.85,
        "createdAt": "2024-01-01T00:00:00Z",
        ...
      }
    ]
  }
}
```

### Predictions

#### Predict Callback
```http
POST /predictions/callback
Authorization: Bearer <token>
Content-Type: application/json

{
  "resumeId": "resume-uuid",
  "jobDescription": "Senior Software Engineer position..."
}

Response: 200
{
  "success": true,
  "data": {
    "score": 0.82,
    "confidence": 0.85,
    "factors": {
      "atsScore": 0.85,
      "experienceRelevance": 0.78,
      "keywordAlignment": 0.83,
      "impactDemonstration": 0.82
    },
    "interpretation": "Good - Strong chance of callback"
  }
}
```

### Subscriptions

#### Create Checkout Session
```http
POST /subscriptions/checkout
Authorization: Bearer <token>
Content-Type: application/json

{
  "tier": "PRO"
}

Response: 200
{
  "success": true,
  "data": {
    "sessionUrl": "https://checkout.stripe.com/..."
  }
}
```

#### Get Subscription
```http
GET /subscriptions
Authorization: Bearer <token>

Response: 200
{
  "success": true,
  "data": {
    "id": "uuid",
    "tier": "PRO",
    "status": "ACTIVE",
    "currentPeriodEnd": "2024-02-01T00:00:00Z"
  }
}
```

#### Cancel Subscription
```http
POST /subscriptions/cancel
Authorization: Bearer <token>

Response: 200
{
  "success": true,
  "data": {
    "cancelAtPeriodEnd": true,
    ...
  }
}
```

### Teams (Enterprise)

#### Create Team
```http
POST /teams
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "Engineering Team",
  "maxMembers": 20
}

Response: 201
{
  "success": true,
  "data": {
    "id": "uuid",
    "name": "Engineering Team",
    "ownerId": "user-uuid",
    "maxMembers": 20
  }
}
```

#### Get Teams
```http
GET /teams
Authorization: Bearer <token>

Response: 200
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "name": "Engineering Team",
      "members": [ ... ]
    }
  ]
}
```

#### Add Team Member
```http
POST /teams/:id/members
Authorization: Bearer <token>
Content-Type: application/json

{
  "email": "member@example.com",
  "role": "member"
}

Response: 201
{
  "success": true,
  "data": {
    "id": "uuid",
    "teamId": "team-uuid",
    "userId": "user-uuid",
    "role": "member"
  }
}
```

### Admin (Admin Only)

#### Get Dashboard Stats
```http
GET /admin/stats
Authorization: Bearer <admin-token>

Response: 200
{
  "success": true,
  "data": {
    "stats": {
      "totalUsers": 1000,
      "totalResumes": 5000,
      "activeSubscriptions": 250,
      "monthlyRevenue": 7450
    },
    "recentUsers": [ ... ]
  }
}
```

#### Get All Users
```http
GET /admin/users?page=1&limit=20
Authorization: Bearer <admin-token>

Response: 200
{
  "success": true,
  "data": {
    "users": [ ... ],
    "pagination": {
      "total": 1000,
      "page": 1,
      "limit": 20,
      "pages": 50
    }
  }
}
```

## Error Responses

All endpoints may return error responses in the following format:

```json
{
  "success": false,
  "message": "Error message here"
}
```

Common HTTP status codes:
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `500` - Internal Server Error

## Rate Limiting

API requests are rate-limited to 100 requests per 15 minutes per IP address.