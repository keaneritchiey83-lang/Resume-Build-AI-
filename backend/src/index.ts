import express, { Application } from 'express';
import cors from 'cors';
import dotenv from 'dotenv';
import authRoutes from './routes/auth.routes';
import resumeRoutes from './routes/resume.routes';
import subscriptionRoutes from './routes/subscription.routes';
import atsRoutes from './routes/ats.routes';
import adminRoutes from './routes/admin.routes';
import teamRoutes from './routes/team.routes';
import predictionRoutes from './routes/prediction.routes';
import { errorHandler } from './middleware/errorHandler';
import { rateLimit } from './middleware/rateLimit';

dotenv.config();

const app: Application = express();
const PORT = process.env.PORT || 5000;

// Global rate limiting for all routes
// Limits requests per IP address to prevent abuse
app.use(rateLimit({
  windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '900000'), // 15 minutes
  maxRequests: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS || '100'),
}));

// Middleware
app.use(cors({
  origin: process.env.CORS_ORIGIN || 'http://localhost:3000',
  credentials: true,
}));
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

// API Routes
app.use('/api/auth', authRoutes);
app.use('/api/resumes', resumeRoutes);
app.use('/api/subscriptions', subscriptionRoutes);
app.use('/api/ats', atsRoutes);
app.use('/api/admin', adminRoutes);
app.use('/api/teams', teamRoutes);
app.use('/api/predictions', predictionRoutes);

// Error handling middleware
app.use(errorHandler);

// Start server only if not in test environment
if (process.env.NODE_ENV !== 'test') {
  app.listen(PORT, () => {
    console.log(`🚀 Server running on port ${PORT}`);
    console.log(`📊 Environment: ${process.env.NODE_ENV}`);
  });
}

export default app;
