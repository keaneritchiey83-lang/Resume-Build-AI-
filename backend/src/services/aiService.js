const OpenAI = require('openai');
const logger = require('../config/logger');

let openai;

/**
 * Get or create OpenAI client
 */
function getOpenAIClient() {
  if (!openai) {
    openai = new OpenAI({
      apiKey: process.env.OPENAI_API_KEY || 'test-key',
    });
  }
  return openai;
}

/**
 * Generate resume content based on job description and user experience
 * @param {Object} params - Parameters for resume generation
 * @returns {Promise<Object>} Generated resume content
 */
async function generateResumeContent(params) {
  const { jobDescription, experience, resumeType = 'private' } = params;

  try {
    const prompt = resumeType === 'federal'
      ? `Generate a federal resume (USAJOBS-compliant) based on:
Job Description: ${jobDescription}
Experience: ${JSON.stringify(experience)}

Include:
- Detailed duty narratives with hours per week
- Quantified achievements
- Federal keywords (RMF, NIST, DoD frameworks)
- KSAs alignment
- Compliance documentation`
      : `Generate a 2-page private sector resume based on:
Job Description: ${jobDescription}
Experience: ${JSON.stringify(experience)}

Include:
- Executive summary (3-5 impact lines)
- Core competencies (keyword-dense)
- Quantified achievements with metrics
- ATS-optimized formatting`;

    const client = getOpenAIClient();
    const response = await client.chat.completions.create({
      model: 'gpt-4',
      messages: [
        {
          role: 'system',
          content: 'You are an expert resume writer specializing in ATS optimization and federal resumes.',
        },
        { role: 'user', content: prompt },
      ],
      temperature: 0.7,
      max_tokens: 2000,
    });

    return {
      content: response.choices[0].message.content,
      usage: response.usage,
    };
  } catch (error) {
    logger.error('Error generating resume content:', error);
    throw new Error('Failed to generate resume content');
  }
}

/**
 * Extract ATS keywords from job description
 * @param {string} jobDescription - Job description text
 * @returns {Promise<Array>} Array of keywords
 */
async function extractATSKeywords(jobDescription) {
  try {
    const client = getOpenAIClient();
    const response = await client.chat.completions.create({
      model: 'gpt-4',
      messages: [
        {
          role: 'system',
          content: 'You are an ATS optimization expert. Extract key skills, technologies, and qualifications that ATS systems look for.',
        },
        {
          role: 'user',
          content: `Extract ATS keywords from this job description:\n${jobDescription}\n\nReturn as a JSON array of strings.`,
        },
      ],
      temperature: 0.3,
      max_tokens: 500,
    });

    const { content } = response.choices[0].message;
    return JSON.parse(content);
  } catch (error) {
    logger.error('Error extracting ATS keywords:', error);
    throw new Error('Failed to extract ATS keywords');
  }
}

/**
 * Optimize resume content for ATS
 * @param {string} resumeContent - Original resume content
 * @param {Array} keywords - Target keywords
 * @returns {Promise<string>} Optimized resume content
 */
async function optimizeResumeForATS(resumeContent, keywords) {
  try {
    const client = getOpenAIClient();
    const response = await client.chat.completions.create({
      model: 'gpt-4',
      messages: [
        {
          role: 'system',
          content: 'You are an ATS optimization expert. Optimize resume content to include relevant keywords naturally.',
        },
        {
          role: 'user',
          content: `Optimize this resume to include these keywords: ${keywords.join(', ')}\n\nResume:\n${resumeContent}`,
        },
      ],
      temperature: 0.5,
      max_tokens: 2000,
    });

    return response.choices[0].message.content;
  } catch (error) {
    logger.error('Error optimizing resume:', error);
    throw new Error('Failed to optimize resume');
  }
}

/**
 * Generate interview questions based on job description
 * @param {Object} params - Parameters for question generation
 * @returns {Promise<Array>} Array of interview questions
 */
async function generateInterviewQuestions(params) {
  const { jobDescription, interviewType = 'behavioral' } = params;

  try {
    let systemPrompt = '';
    let userPrompt = '';

    switch (interviewType) {
      case 'behavioral':
        systemPrompt = 'You are an interview coach specializing in behavioral interviews using the STAR method.';
        userPrompt = `Generate 10 behavioral interview questions with STAR method guidance for this job:\n${jobDescription}`;
        break;
      case 'technical':
        systemPrompt = 'You are a technical interview expert.';
        userPrompt = `Generate 10 technical interview questions with expected answer guidance for this job:\n${jobDescription}`;
        break;
      case 'federal':
        systemPrompt = 'You are a federal interview expert specializing in structured performance-based questions.';
        userPrompt = `Generate 10 federal panel interview questions with CCAR method guidance for this job:\n${jobDescription}`;
        break;
      default:
        throw new Error('Invalid interview type');
    }

    const client = getOpenAIClient();
    const response = await client.chat.completions.create({
      model: 'gpt-4',
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: `${userPrompt}\n\nReturn as JSON array with structure: [{question: string, guidance: string}]` },
      ],
      temperature: 0.7,
      max_tokens: 2000,
    });

    const { content } = response.choices[0].message;
    return JSON.parse(content);
  } catch (error) {
    logger.error('Error generating interview questions:', error);
    throw new Error('Failed to generate interview questions');
  }
}

/**
 * Quantify achievements in experience descriptions
 * @param {string} description - Original description
 * @returns {Promise<string>} Quantified description
 */
async function quantifyAchievements(description) {
  try {
    const client = getOpenAIClient();
    const response = await client.chat.completions.create({
      model: 'gpt-4',
      messages: [
        {
          role: 'system',
          content: 'You are an expert at converting generic task descriptions into quantified, impact-driven achievements.',
        },
        {
          role: 'user',
          content: `Convert this description into a quantified achievement with metrics:\n${description}`,
        },
      ],
      temperature: 0.6,
      max_tokens: 200,
    });

    return response.choices[0].message.content;
  } catch (error) {
    logger.error('Error quantifying achievements:', error);
    throw new Error('Failed to quantify achievements');
  }
}

/**
 * Analyze skill gaps based on job requirements
 * @param {Array} currentSkills - User's current skills
 * @param {string} jobDescription - Target job description
 * @returns {Promise<Object>} Skill gap analysis
 */
async function analyzeSkillGap(currentSkills, jobDescription) {
  try {
    const client = getOpenAIClient();
    const response = await client.chat.completions.create({
      model: 'gpt-4',
      messages: [
        {
          role: 'system',
          content: 'You are a career advisor specializing in skill gap analysis.',
        },
        {
          role: 'user',
          content: `Analyze skill gaps:\nCurrent Skills: ${currentSkills.join(', ')}\nJob Requirements: ${jobDescription}\n\nReturn JSON: {missing: [], recommendations: []}`,
        },
      ],
      temperature: 0.5,
      max_tokens: 1000,
    });

    const { content } = response.choices[0].message;
    return JSON.parse(content);
  } catch (error) {
    logger.error('Error analyzing skill gap:', error);
    throw new Error('Failed to analyze skill gap');
  }
}

module.exports = {
  generateResumeContent,
  extractATSKeywords,
  optimizeResumeForATS,
  generateInterviewQuestions,
  quantifyAchievements,
  analyzeSkillGap,
  // For testing
  _resetClient: () => { openai = null; },
};
