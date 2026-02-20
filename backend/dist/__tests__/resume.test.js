"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const supertest_1 = __importDefault(require("supertest"));
const index_1 = __importDefault(require("../index"));
// Mock the entire Prisma module and the controllers
jest.mock('@prisma/client');
jest.mock('jsonwebtoken');
describe('Resume Routes', () => {
    describe('POST /api/resumes - unauthenticated', () => {
        it('should return 401 without authentication', async () => {
            const response = await (0, supertest_1.default)(index_1.default)
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
            const response = await (0, supertest_1.default)(index_1.default)
                .get('/api/resumes');
            expect(response.status).toBe(401);
            expect(response.body).toHaveProperty('message');
        });
    });
    describe('GET /api/resumes/:id - unauthenticated', () => {
        it('should return 401 without authentication', async () => {
            const response = await (0, supertest_1.default)(index_1.default)
                .get('/api/resumes/test-id');
            expect(response.status).toBe(401);
            expect(response.body).toHaveProperty('message');
        });
    });
    describe('PUT /api/resumes/:id - unauthenticated', () => {
        it('should return 401 without authentication', async () => {
            const response = await (0, supertest_1.default)(index_1.default)
                .put('/api/resumes/test-id')
                .send({ title: 'Updated' });
            expect(response.status).toBe(401);
            expect(response.body).toHaveProperty('message');
        });
    });
    describe('DELETE /api/resumes/:id - unauthenticated', () => {
        it('should return 401 without authentication', async () => {
            const response = await (0, supertest_1.default)(index_1.default)
                .delete('/api/resumes/test-id');
            expect(response.status).toBe(401);
            expect(response.body).toHaveProperty('message');
        });
    });
});
//# sourceMappingURL=resume.test.js.map