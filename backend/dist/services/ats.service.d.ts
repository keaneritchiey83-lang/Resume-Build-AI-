export interface ATSScoreResult {
    overallScore: number;
    keywordScore: number;
    semanticScore: number;
    impactScore: number;
    suggestions: string[];
    matchedKeywords: string[];
    missingKeywords: string[];
}
export declare class ATSEngine {
    /**
     * Analyze resume against job description
     */
    static analyzeResume(resumeText: string, jobDescription: string): ATSScoreResult;
    /**
     * Calculate keyword match score
     */
    private static calculateKeywordMatch;
    /**
     * Calculate semantic similarity using TF-IDF
     */
    private static calculateSemanticSimilarity;
    /**
     * Calculate impact score based on action verbs and metrics
     */
    private static calculateImpactScore;
    /**
     * Extract important keywords (nouns, adjectives, verbs)
     */
    private static extractKeywords;
    /**
     * Get detailed keyword analysis
     */
    private static getKeywordAnalysis;
    /**
     * Generate improvement suggestions
     */
    private static generateSuggestions;
    /**
     * Calculate cosine similarity between two vectors
     */
    private static cosineSimilarity;
}
//# sourceMappingURL=ats.service.d.ts.map