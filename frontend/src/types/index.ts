export interface User {
  id: string;
  email: string;
  firstName?: string;
  lastName?: string;
  role: 'USER' | 'ADMIN' | 'TEAM_ADMIN';
  subscription?: Subscription;
  createdAt: string;
}

export interface Subscription {
  id: string;
  tier: 'FREE' | 'PRO' | 'ENTERPRISE';
  status: 'ACTIVE' | 'INACTIVE' | 'CANCELED' | 'PAST_DUE';
  currentPeriodEnd?: string;
  cancelAtPeriodEnd: boolean;
}

export interface Resume {
  id: string;
  userId: string;
  title: string;
  template: string;
  content: ResumeContent;
  atsScore?: number;
  keywordMatches?: {
    matched: string[];
    missing: string[];
  };
  impactScore?: number;
  isPublic: boolean;
  createdAt: string;
  updatedAt: string;
  atsAnalyses?: ATSAnalysis[];
}

export interface ResumeContent {
  personalInfo?: {
    name?: string;
    email?: string;
    phone?: string;
    location?: string;
    title?: string;
    linkedin?: string;
    website?: string;
  };
  summary?: string;
  experience?: Experience[];
  education?: Education[];
  skills?: string[];
  certifications?: Certification[];
  projects?: Project[];
}

export interface Experience {
  id: string;
  title: string;
  company: string;
  location?: string;
  startDate: string;
  endDate?: string;
  current: boolean;
  description?: string;
  achievements?: string[];
}

export interface Education {
  id: string;
  degree: string;
  school: string;
  location?: string;
  startDate: string;
  endDate?: string;
  gpa?: string;
  description?: string;
}

export interface Certification {
  id: string;
  name: string;
  issuer: string;
  date: string;
  expiryDate?: string;
  credentialId?: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  technologies?: string[];
  url?: string;
  startDate?: string;
  endDate?: string;
}

export interface ATSAnalysis {
  id: string;
  resumeId: string;
  jobDescription: string;
  overallScore: number;
  keywordScore: number;
  semanticScore: number;
  impactScore: number;
  suggestions: string[];
  createdAt: string;
}

export interface CallbackPrediction {
  score: number;
  confidence: number;
  factors: {
    atsScore: number;
    experienceRelevance: number;
    keywordAlignment: number;
    impactDemonstration: number;
  };
  interpretation: string;
}

export interface Team {
  id: string;
  name: string;
  ownerId: string;
  subscriptionTier: 'FREE' | 'PRO' | 'ENTERPRISE';
  maxMembers: number;
  createdAt: string;
  updatedAt: string;
  members?: TeamMember[];
  owner?: User;
}

export interface TeamMember {
  id: string;
  teamId: string;
  userId: string;
  role: string;
  joinedAt: string;
  user?: User;
}
