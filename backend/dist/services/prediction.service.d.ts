import { Resume, ATSAnalysis } from '@prisma/client';
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
export declare class CallbackPredictor {
    /**
     * Predict likelihood of getting a callback based on resume and job description
     */
    static predict(resume: Resume & {
        atsAnalyses: ATSAnalysis[];
    }, jobDescription: string): CallbackPrediction;
    /**
     * Calculate how relevant the experience is
     */
    private static calculateExperienceRelevance;
    /**
     * Extract industry-specific keywords
     */
    private static extractIndustryKeywords;
    /**
     * Match seniority level
     */
    private static matchSeniority;
    /**
     * Interpret the prediction score
     */
    private static interpretScore;
}
//# sourceMappingURL=prediction.service.d.ts.map