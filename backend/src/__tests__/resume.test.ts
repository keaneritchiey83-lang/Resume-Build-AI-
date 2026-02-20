import request from 'supertest';
import app from '../index';

// Mock the entire Prisma module and the controllers
jest.mock('@prisma/client');
jest.mock('jsonwebtoken');

describe('Resume Routes', () => {
  describe('POST /api/resumes - unauthenticated', () => {
    it('should return 401 without authentication', async () => {
      const response = await request(app)
        .post('/api/resumes')
        .send({
          title: 'Test Resume',
          content: {},
        });

      expect(response.status).toBe(401);
      expect(response.body).toHaveProperty('message');
    });
  });

  describe('GET /api/resumes - unauthenticated', () => {
    it('should return 401 without authentication', async () => {
      const response = await request(app)
        .get('/api/resumes');

      expect(response.status).toBe(401);
      expect(response.body).toHaveProperty('message');
    });
  });

  describe('GET /api/resumes/:id - unauthenticated', () => {
    it('should return 401 without authentication', async () => {
      const response = await request(app)
        .get('/api/resumes/test-id');

      expect(response.status).toBe(401);
      expect(response.body).toHaveProperty('message');
    });
  });

  describe('PUT /api/resumes/:id - unauthenticated', () => {
    it('should return 401 without authentication', async () => {
      const response = await request(app)
        .put('/api/resumes/test-id')
        .send({ title: 'Updated' });

      expect(response.status).toBe(401);
      expect(response.body).toHaveProperty('message');
    });
  });

  describe('DELETE /api/resumes/:id - unauthenticated', () => {
    it('should return 401 without authentication', async () => {
      const response = await request(app)
        .delete('/api/resumes/test-id');

      expect(response.status).toBe(401);
      expect(response.body).toHaveProperty('message');
    });
  });
});

