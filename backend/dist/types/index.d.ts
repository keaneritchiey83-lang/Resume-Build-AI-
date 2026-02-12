export interface PersonalInfo {
    name?: string;
    title?: string;
    email?: string;
    phone?: string;
    location?: string;
}
export interface Experience {
    title?: string;
    company?: string;
    description?: string;
    achievements?: string[];
    startDate?: string;
    endDate?: string;
}
export interface Education {
    degree?: string;
    school?: string;
    graduationDate?: string;
}
export interface ResumeContent {
    personalInfo?: PersonalInfo;
    summary?: string;
    experience?: Experience[];
    education?: Education[];
    skills?: string[];
}
export interface ErrorWithStatus extends Error {
    status?: number;
    statusCode?: number;
}
//# sourceMappingURL=index.d.ts.map