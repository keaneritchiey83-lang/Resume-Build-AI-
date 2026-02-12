const OpenAI = require('openai');
const aiService = require('../src/services/aiService');

// Mock OpenAI
jest.mock('openai');

describe('AI Service', () => {
  let mockCreate;

  beforeEach(() => {
    jest.clearAllMocks();
    aiService._resetClient(); // Reset the OpenAI client between tests
    mockCreate = jest.fn();
    OpenAI.mockImplementation(() => ({
      chat: {
        completions: {
          create: mockCreate,
        },
      },
    }));
  });

  describe('generateResumeContent', () => {
    it('should generate resume content', async () => {
      const mockResponse = {
        choices: [{ message: { content: 'Generated resume' } }],
        usage: { total_tokens: 100 },
      };

      mockCreate.mockResolvedValueOnce(mockResponse);

      const result = await aiService.generateResumeContent({
        jobDescription: 'Software Engineer',
        experience: [{ title: 'Developer', years: 3 }],
        resumeType: 'private',
      });

      expect(result.content).toBe('Generated resume');
      expect(result.usage).toEqual({ total_tokens: 100 });
    });

    it('should handle errors gracefully', async () => {
      mockCreate.mockRejectedValueOnce(new Error('API error'));

      await expect(
        aiService.generateResumeContent({
          jobDescription: 'Software Engineer',
          experience: [],
          resumeType: 'private',
        }),
      ).rejects.toThrow('Failed to generate resume content');
    });
  });

  describe('extractATSKeywords', () => {
    it('should extract keywords from job description', async () => {
      const mockKeywords = ['JavaScript', 'React', 'Node.js'];
      const mockResponse = {
        choices: [{ message: { content: JSON.stringify(mockKeywords) } }],
      };

      mockCreate.mockResolvedValueOnce(mockResponse);

      const result = await aiService.extractATSKeywords('Software Engineer job');

      expect(result).toEqual(mockKeywords);
    });
  });

  describe('generateInterviewQuestions', () => {
    it('should generate behavioral interview questions', async () => {
      const mockQuestions = [
        { question: 'Tell me about...', guidance: 'Use STAR' },
      ];
      const mockResponse = {
        choices: [{ message: { content: JSON.stringify(mockQuestions) } }],
      };

      mockCreate.mockResolvedValueOnce(mockResponse);

      const result = await aiService.generateInterviewQuestions({
        jobDescription: 'Software Engineer',
        interviewType: 'behavioral',
      });

      expect(result).toEqual(mockQuestions);
    });

    it('should throw error for invalid interview type', async () => {
      await expect(
        aiService.generateInterviewQuestions({
          jobDescription: 'Software Engineer',
          interviewType: 'invalid',
        }),
      ).rejects.toThrow();
    });
  });

  describe('analyzeSkillGap', () => {
    it('should analyze skill gaps', async () => {
      const mockAnalysis = {
        missing: ['Docker', 'Kubernetes'],
        recommendations: ['Learn containerization'],
      };
      const mockResponse = {
        choices: [{ message: { content: JSON.stringify(mockAnalysis) } }],
      };

      mockCreate.mockResolvedValueOnce(mockResponse);

      const result = await aiService.analyzeSkillGap(
        ['JavaScript', 'React'],
        'DevOps Engineer',
      );

      expect(result).toEqual(mockAnalysis);
    });
  });
});
