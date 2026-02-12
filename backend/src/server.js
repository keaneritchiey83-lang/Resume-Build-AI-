require('dotenv').config();
const app = require('./app');
const logger = require('./config/logger');
const { initDatabase } = require('./models/init');

const PORT = process.env.PORT || 3000;

async function startServer() {
  try {
    // Initialize database
    if (process.env.NODE_ENV !== 'test') {
      await initDatabase();
      logger.info('Database initialized');
    }

    // Start server
    const server = app.listen(PORT, () => {
      logger.info(`Server running on port ${PORT}`);
      logger.info(`Environment: ${process.env.NODE_ENV || 'development'}`);
    });

    // Graceful shutdown
    process.on('SIGTERM', () => {
      logger.info('SIGTERM received, closing server gracefully');
      server.close(() => {
        logger.info('Server closed');
        process.exit(0);
      });
    });
  } catch (error) {
    logger.error('Failed to start server:', error);
    process.exit(1);
  }
}

startServer();
