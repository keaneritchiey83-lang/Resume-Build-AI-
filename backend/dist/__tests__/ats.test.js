"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const ats_service_1 = require("../services/ats.service");
// Mock natural library
jest.mock('natural', () => {
    const mockTfIdf = jest.fn().mockImplementation(() => ({
        addDocument: jest.fn(),
        listTerms: jest.fn(() => [
            { term: 'developer', tfidf: 0.5 },
            { term: 'software', tfidf: 0.4 },
        ]),
        tfidf: jest.fn(() => 0.3),
    }));
    return {
        TfIdf: mockTfIdf,
        WordTokenizer: jest.fn().mockImplementation(() => ({
            tokenize: jest.fn((text) => text.split(' ')),
        })),
    };
});
describe('ATS Service', () => {
    describe('analyzeResume', () => {
        it('should analyze resume and return scores', () => {
            const resumeText = `
        • Developed and implemented software solutions
        • Improved system performance by 30%
        • Led team of 5 developers
        • Generated $500K in revenue
      `;
            const jobDescription = 'Software Developer with experience in development and leadership';
            const result = ats_service_1.ATSEngine.analyzeResume(resumeText, jobDescription);
            expect(result).toHaveProperty('overallScore');
            expect(result).toHaveProperty('keywordScore');
            expect(result).toHaveProperty('semanticScore');
            expect(result).toHaveProperty('impactScore');
            expect(result).toHaveProperty('suggestions');
            expect(result).toHaveProperty('matchedKeywords');
            expect(result).toHaveProperty('missingKeywords');
            expect(typeof result.overallScore).toBe('number');
            expect(result.overallScore).toBeGreaterThanOrEqual(0);
            expect(result.overallScore).toBeLessThanOrEqual(1);
        });
        it('should detect impact verbs and metrics', () => {
            const resumeText = `
        • Improved efficiency by 40%
        • Developed new features
        • Led team of 10 people
        • Reduced costs by $100K
      `;
            const jobDescription = 'Looking for experienced developer';
            const result = ats_service_1.ATSEngine.analyzeResume(resumeText, jobDescription);
            // Should have good impact score due to verbs and metrics
            expect(result.impactScore).toBeGreaterThan(0);
        });
        it('should provide suggestions for low scores', () => {
            const resumeText = 'I worked on some projects.';
            const jobDescription = 'Software Engineer with Python, React, AWS experience';
            const result = ats_service_1.ATSEngine.analyzeResume(resumeText, jobDescription);
            expect(result.suggestions.length).toBeGreaterThan(0);
            expect(result.suggestions.some(s => s.includes('keywords'))).toBe(true);
        });
        it('should identify matched and missing keywords', () => {
            const resumeText = 'Software developer with Python experience';
            const jobDescription = 'Software developer with Python and Java experience required';
            const result = ats_service_1.ATSEngine.analyzeResume(resumeText, jobDescription);
            expect(result.matchedKeywords).toContain('software');
            expect(result.matchedKeywords).toContain('python');
            expect(Array.isArray(result.missingKeywords)).toBe(true);
        });
        it('should handle empty inputs gracefully', () => {
            const result = ats_service_1.ATSEngine.analyzeResume('', '');
            expect(typeof result.overallScore).toBe('number');
            expect(result.overallScore).toBeGreaterThanOrEqual(0);
            expect(result.overallScore).toBeLessThanOrEqual(1);
            expect(result.keywordScore).toBe(0);
            expect(result.impactScore).toBe(0);
        });
    });
});
//# sourceMappingURL=ats.test.js.map