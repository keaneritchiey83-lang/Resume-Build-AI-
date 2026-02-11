import natural from 'natural';

const TfIdf = natural.TfIdf;
const tokenizer = new natural.WordTokenizer();

export interface ATSScoreResult {
  overallScore: number;
  keywordScore: number;
  semanticScore: number;
  impactScore: number;
  suggestions: string[];
  matchedKeywords: string[];
  missingKeywords: string[];
}

// Common action verbs that demonstrate impact
const IMPACT_VERBS = [
  'achieved', 'improved', 'increased', 'decreased', 'reduced', 'generated',
  'launched', 'developed', 'implemented', 'managed', 'led', 'created',
  'designed', 'optimized', 'streamlined', 'established', 'transformed',
  'delivered', 'exceeded', 'accelerated', 'resolved', 'enhanced', 'built',
];

// Regex for quantifiable metrics
const METRIC_PATTERNS = [
  /\d+%/,                          // Percentages
  /\$[\d,]+/,                      // Dollar amounts
  /\d+[kKmMbB]/,                   // Numbers with K, M, B suffix
  /\d+\s*(hours?|days?|weeks?|months?|years?)/i,  // Time periods
  /\d+\s*(people|users|customers|clients)/i,      // People counts
];

export class ATSEngine {
  /**
   * Analyze resume against job description
   */
  static analyzeResume(resumeText: string, jobDescription: string): ATSScoreResult {
    const keywordScore = this.calculateKeywordMatch(resumeText, jobDescription);
    const semanticScore = this.calculateSemanticSimilarity(resumeText, jobDescription);
    const impactScore = this.calculateImpactScore(resumeText);
    
    // Weight the scores
    const overallScore = (
      keywordScore * 0.4 +
      semanticScore * 0.35 +
      impactScore * 0.25
    );

    const suggestions = this.generateSuggestions(resumeText, jobDescription, {
      keywordScore,
      semanticScore,
      impactScore,
    });

    const { matched, missing } = this.getKeywordAnalysis(resumeText, jobDescription);

    return {
      overallScore: Math.round(overallScore * 100) / 100,
      keywordScore: Math.round(keywordScore * 100) / 100,
      semanticScore: Math.round(semanticScore * 100) / 100,
      impactScore: Math.round(impactScore * 100) / 100,
      suggestions,
      matchedKeywords: matched,
      missingKeywords: missing,
    };
  }

  /**
   * Calculate keyword match score
   */
  private static calculateKeywordMatch(resumeText: string, jobDescription: string): number {
    const resumeTokens = this.extractKeywords(resumeText.toLowerCase());
    const jobTokens = this.extractKeywords(jobDescription.toLowerCase());

    if (jobTokens.length === 0) return 0;

    const matchedCount = jobTokens.filter(token => 
      resumeTokens.includes(token)
    ).length;

    return matchedCount / jobTokens.length;
  }

  /**
   * Calculate semantic similarity using TF-IDF
   */
  private static calculateSemanticSimilarity(resumeText: string, jobDescription: string): number {
    const tfidf = new TfIdf();
    tfidf.addDocument(resumeText);
    tfidf.addDocument(jobDescription);

    // Calculate cosine similarity between documents
    const resumeVector: number[] = [];
    const jobVector: number[] = [];
    const allTerms = new Set<string>();

    // Collect all terms
    tfidf.listTerms(0).forEach(item => allTerms.add(item.term));
    tfidf.listTerms(1).forEach(item => allTerms.add(item.term));

    // Build vectors
    allTerms.forEach(term => {
      resumeVector.push(tfidf.tfidf(term, 0));
      jobVector.push(tfidf.tfidf(term, 1));
    });

    return this.cosineSimilarity(resumeVector, jobVector);
  }

  /**
   * Calculate impact score based on action verbs and metrics
   */
  private static calculateImpactScore(resumeText: string): number {
    const lines = resumeText.split('\n').filter(line => line.trim().length > 0);
    let totalScore = 0;
    let bulletPoints = 0;

    for (const line of lines) {
      // Check if it's likely a bullet point (starts with bullet or dash)
      if (line.trim().match(/^[•\-\*]/)) {
        bulletPoints++;
        let lineScore = 0;

        // Check for impact verbs
        const hasImpactVerb = IMPACT_VERBS.some(verb => 
          line.toLowerCase().includes(verb)
        );
        if (hasImpactVerb) lineScore += 0.5;

        // Check for metrics
        const hasMetrics = METRIC_PATTERNS.some(pattern => 
          pattern.test(line)
        );
        if (hasMetrics) lineScore += 0.5;

        totalScore += Math.min(lineScore, 1);
      }
    }

    return bulletPoints > 0 ? totalScore / bulletPoints : 0;
  }

  /**
   * Extract important keywords (nouns, adjectives, verbs)
   */
  private static extractKeywords(text: string): string[] {
    const tokens = tokenizer.tokenize(text) || [];
    
    // Filter out common words and short tokens
    const stopWords = new Set([
      'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
      'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
      'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
      'would', 'should', 'could', 'may', 'might', 'can', 'must',
    ]);

    return tokens.filter(token => 
      token.length > 2 && !stopWords.has(token.toLowerCase())
    );
  }

  /**
   * Get detailed keyword analysis
   */
  private static getKeywordAnalysis(resumeText: string, jobDescription: string) {
    const resumeKeywords = new Set(this.extractKeywords(resumeText.toLowerCase()));
    const jobKeywords = this.extractKeywords(jobDescription.toLowerCase());

    const matched: string[] = [];
    const missing: string[] = [];

    jobKeywords.forEach(keyword => {
      if (resumeKeywords.has(keyword)) {
        matched.push(keyword);
      } else {
        missing.push(keyword);
      }
    });

    return { matched: [...new Set(matched)], missing: [...new Set(missing)].slice(0, 20) };
  }

  /**
   * Generate improvement suggestions
   */
  private static generateSuggestions(
    resumeText: string,
    jobDescription: string,
    scores: { keywordScore: number; semanticScore: number; impactScore: number }
  ): string[] {
    const suggestions: string[] = [];

    if (scores.keywordScore < 0.5) {
      const { missing } = this.getKeywordAnalysis(resumeText, jobDescription);
      suggestions.push(
        `Include more relevant keywords from the job description: ${missing.slice(0, 5).join(', ')}`
      );
    }

    if (scores.impactScore < 0.6) {
      suggestions.push(
        'Add more quantifiable achievements with specific metrics (%, $, numbers)'
      );
      suggestions.push(
        `Start bullet points with strong action verbs: ${IMPACT_VERBS.slice(0, 5).join(', ')}`
      );
    }

    if (scores.semanticScore < 0.5) {
      suggestions.push(
        'Better align your experience descriptions with the job requirements'
      );
    }

    if (resumeText.length < 500) {
      suggestions.push(
        'Expand your resume with more details about your experience and achievements'
      );
    }

    return suggestions;
  }

  /**
   * Calculate cosine similarity between two vectors
   */
  private static cosineSimilarity(vec1: number[], vec2: number[]): number {
    if (vec1.length !== vec2.length || vec1.length === 0) return 0;

    let dotProduct = 0;
    let mag1 = 0;
    let mag2 = 0;

    for (let i = 0; i < vec1.length; i++) {
      dotProduct += vec1[i] * vec2[i];
      mag1 += vec1[i] * vec1[i];
      mag2 += vec2[i] * vec2[i];
    }

    mag1 = Math.sqrt(mag1);
    mag2 = Math.sqrt(mag2);

    if (mag1 === 0 || mag2 === 0) return 0;

    return dotProduct / (mag1 * mag2);
  }
}
