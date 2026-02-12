const request = require('supertest');
const app = require('../src/app');
const aiService = require('../src/services/aiService');

// Mock the AI service
jest.mock('../src/services/aiService');

describe('Resume API', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('POST /api/resume/generate', () => {
    it('should generate a resume successfully', async () => {
      const mockResult = {
        content: 'Generated resume content',
        usage: { total_tokens: 100 },
      };

      aiService.generateResumeContent.mockResolvedValue(mockResult);

      const response = await request(app)
        .post('/api/resume/generate')
        .send({
          jobDescription: 'Software Engineer position',
          experience: [{ title: 'Developer', years: 3 }],
          resumeType: 'private',
        })
        .expect('Content-Type', /json/)
        .expect(200);

      expect(response.body.success).toBe(true);
      expect(response.body.data).toEqual(mockResult);
      expect(aiService.generateResumeContent).toHaveBeenCalledWith({
        jobDescription: 'Software Engineer position',
        experience: [{ title: 'Developer', years: 3 }],
        resumeType: 'private',
      });
    });

    it('should return 400 for missing jobDescription', async () => {
      const response = await request(app)
        .post('/api/resume/generate')
        .send({
          experience: [{ title: 'Developer', years: 3 }],
        })
        .expect('Content-Type', /json/)
        .expect(400);

      expect(response.body.success).toBe(false);
      expect(response.body.errors).toBeDefined();
    });

    it('should return 400 for invalid resumeType', async () => {
      const response = await request(app)
        .post('/api/resume/generate')
        .send({
          jobDescription: 'Software Engineer position',
          experience: [{ title: 'Developer', years: 3 }],
          resumeType: 'invalid',
        })
        .expect('Content-Type', /json/)
        .expect(400);

      expect(response.body.success).toBe(false);
      expect(response.body.errors).toBeDefined();
    });
  });

  describe('POST /api/resume/optimize', () => {
    it('should optimize a resume successfully', async () => {
      const mockKeywords = ['JavaScript', 'React', 'Node.js'];
      const mockOptimizedContent = 'Optimized resume content';

      aiService.extractATSKeywords.mockResolvedValue(mockKeywords);
      aiService.optimizeResumeForATS.mockResolvedValue(mockOptimizedContent);

      const response = await request(app)
        .post('/api/resume/optimize')
        .send({
          resumeContent: 'Original resume content',
          jobDescription: 'Software Engineer position',
        })
        .expect('Content-Type', /json/)
        .expect(200);

      expect(response.body.success).toBe(true);
      expect(response.body.data.keywords).toEqual(mockKeywords);
      expect(response.body.data.optimizedContent).toEqual(mockOptimizedContent);
    });

    it('should return 400 for missing resumeContent', async () => {
      const response = await request(app)
        .post('/api/resume/optimize')
        .send({
          jobDescription: 'Software Engineer position',
        })
        .expect('Content-Type', /json/)
        .expect(400);

      expect(response.body.success).toBe(false);
      expect(response.body.errors).toBeDefined();
    });
  });
});
