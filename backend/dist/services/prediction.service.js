"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.CallbackPredictor = void 0;
class CallbackPredictor {
    /**
     * Predict likelihood of getting a callback based on resume and job description
     */
    static predict(resume, jobDescription) {
        const latestATS = resume.atsAnalyses[0];
        // Calculate individual factors
        const atsScore = latestATS?.overallScore || resume.atsScore || 0;
        const experienceRelevance = this.calculateExperienceRelevance(resume, jobDescription);
        const keywordAlignment = latestATS?.keywordScore || 0;
        const impactDemonstration = latestATS?.impactScore || resume.impactScore || 0;
        // Weighted calculation
        const score = (atsScore * 0.35 +
            experienceRelevance * 0.25 +
            keywordAlignment * 0.25 +
            impactDemonstration * 0.15);
        // Calculate confidence based on data availability
        let confidence = 0.7; // Base confidence
        if (latestATS)
            confidence += 0.2;
        if (resume.atsScore)
            confidence += 0.1;
        const factors = {
            atsScore,
            experienceRelevance,
            keywordAlignment,
            impactDemonstration,
        };
        const interpretation = this.interpretScore(score);
        return {
            score: Math.round(score * 100) / 100,
            confidence: Math.round(confidence * 100) / 100,
            factors,
            interpretation,
        };
    }
    /**
     * Calculate how relevant the experience is
     */
    static calculateExperienceRelevance(resume, jobDescription) {
        const content = resume.content;
        if (!content.experience || !Array.isArray(content.experience)) {
            return 0.3; // Low relevance if no experience data
        }
        const experienceCount = content.experience.length;
        const jobDescLower = jobDescription.toLowerCase();
        let relevanceScore = 0;
        // Check for years of experience mentioned
        const yearsMatch = jobDescription.match(/(\d+)\+?\s*years?/i);
        if (yearsMatch && experienceCount >= parseInt(yearsMatch[1])) {
            relevanceScore += 0.3;
        }
        // Check for industry keywords in experience
        const industryKeywords = this.extractIndustryKeywords(jobDescLower);
        const experienceText = content.experience
            .map((exp) => `${exp.title} ${exp.company} ${exp.description || ''}`)
            .join(' ')
            .toLowerCase();
        const matchedKeywords = industryKeywords.filter(keyword => experienceText.includes(keyword));
        relevanceScore += (matchedKeywords.length / Math.max(industryKeywords.length, 1)) * 0.4;
        // Check for seniority match
        const seniorityMatch = this.matchSeniority(content.experience, jobDescLower);
        relevanceScore += seniorityMatch * 0.3;
        return Math.min(relevanceScore, 1);
    }
    /**
     * Extract industry-specific keywords
     */
    static extractIndustryKeywords(text) {
        const commonKeywords = [
            'software', 'engineer', 'developer', 'manager', 'senior', 'lead',
            'architecture', 'design', 'implementation', 'agile', 'scrum',
            'cloud', 'aws', 'azure', 'kubernetes', 'docker',
            'javascript', 'python', 'java', 'react', 'node',
            'database', 'sql', 'api', 'microservices', 'ci/cd',
        ];
        return commonKeywords.filter(keyword => text.includes(keyword));
    }
    /**
     * Match seniority level
     */
    static matchSeniority(experience, jobDesc) {
        const seniorityLevels = {
            entry: ['entry', 'junior', 'associate', 'graduate'],
            mid: ['mid', 'intermediate'],
            senior: ['senior', 'lead', 'principal', 'staff'],
            executive: ['director', 'vp', 'chief', 'head of'],
        };
        let jobLevel = null;
        for (const [level, keywords] of Object.entries(seniorityLevels)) {
            if (keywords.some(keyword => jobDesc.includes(keyword))) {
                jobLevel = level;
                break;
            }
        }
        if (!jobLevel)
            return 0.5; // Neutral if can't determine
        // Check if resume has appropriate level
        const resumeText = experience
            .map(exp => `${exp.title}`.toLowerCase())
            .join(' ');
        const hasMatchingLevel = seniorityLevels[jobLevel]
            .some(keyword => resumeText.includes(keyword));
        return hasMatchingLevel ? 1 : 0.4;
    }
    /**
     * Interpret the prediction score
     */
    static interpretScore(score) {
        if (score >= 0.8) {
            return 'Excellent - Very high likelihood of callback';
        }
        else if (score >= 0.65) {
            return 'Good - Strong chance of callback';
        }
        else if (score >= 0.5) {
            return 'Moderate - Reasonable chance with improvements';
        }
        else if (score >= 0.35) {
            return 'Fair - Consider significant improvements';
        }
        else {
            return 'Low - Resume needs substantial improvements';
        }
    }
}
exports.CallbackPredictor = CallbackPredictor;
//# sourceMappingURL=prediction.service.js.map