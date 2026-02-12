const request = require('supertest');
const app = require('../src/app');
const aiService = require('../src/services/aiService');

// Mock the AI service
jest.mock('../src/services/aiService');

describe('Interview API', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('POST /api/interview/prepare', () => {
    it('should generate interview questions successfully', async () => {
      const mockQuestions = [
        { question: 'Tell me about a time...', guidance: 'Use STAR method' },
        { question: 'Describe a situation...', guidance: 'Focus on impact' },
      ];

      aiService.generateInterviewQuestions.mockResolvedValue(mockQuestions);

      const response = await request(app)
        .post('/api/interview/prepare')
        .send({
          jobDescription: 'Software Engineer position',
          interviewType: 'behavioral',
        })
        .expect('Content-Type', /json/)
        .expect(200);

      expect(response.body.success).toBe(true);
      expect(response.body.data.questions).toEqual(mockQuestions);
      expect(response.body.data.interviewType).toBe('behavioral');
    });

    it('should return 400 for invalid interviewType', async () => {
      const response = await request(app)
        .post('/api/interview/prepare')
        .send({
          jobDescription: 'Software Engineer position',
          interviewType: 'invalid',
        })
        .expect('Content-Type', /json/)
        .expect(400);

      expect(response.body.success).toBe(false);
      expect(response.body.errors).toBeDefined();
    });

    it('should return 400 for missing jobDescription', async () => {
      const response = await request(app)
        .post('/api/interview/prepare')
        .send({
          interviewType: 'behavioral',
        })
        .expect('Content-Type', /json/)
        .expect(400);

      expect(response.body.success).toBe(false);
      expect(response.body.errors).toBeDefined();
    });
  });
});
