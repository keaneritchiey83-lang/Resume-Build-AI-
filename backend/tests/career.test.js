const request = require('supertest');
const app = require('../src/app');
const aiService = require('../src/services/aiService');

// Mock the AI service
jest.mock('../src/services/aiService');

describe('Career API', () => {
  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('POST /api/career/skills-gap', () => {
    it('should analyze skill gap successfully', async () => {
      const mockAnalysis = {
        missing: ['Kubernetes', 'Docker'],
        recommendations: ['Complete a Docker course', 'Get certified in K8s'],
      };

      aiService.analyzeSkillGap.mockResolvedValue(mockAnalysis);

      const response = await request(app)
        .post('/api/career/skills-gap')
        .send({
          currentSkills: ['JavaScript', 'React', 'Node.js'],
          jobDescription: 'Senior DevOps Engineer position',
        })
        .expect('Content-Type', /json/)
        .expect(200);

      expect(response.body.success).toBe(true);
      expect(response.body.data).toEqual(mockAnalysis);
    });

    it('should return 400 for missing currentSkills', async () => {
      const response = await request(app)
        .post('/api/career/skills-gap')
        .send({
          jobDescription: 'Senior DevOps Engineer position',
        })
        .expect('Content-Type', /json/)
        .expect(400);

      expect(response.body.success).toBe(false);
      expect(response.body.errors).toBeDefined();
    });

    it('should return 400 for empty currentSkills array', async () => {
      const response = await request(app)
        .post('/api/career/skills-gap')
        .send({
          currentSkills: [],
          jobDescription: 'Senior DevOps Engineer position',
        })
        .expect('Content-Type', /json/)
        .expect(400);

      expect(response.body.success).toBe(false);
      expect(response.body.errors).toBeDefined();
    });
  });
});
