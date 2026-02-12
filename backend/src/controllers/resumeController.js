const aiService = require('../services/aiService');
const logger = require('../config/logger');

/**
 * Generate a new resume
 */
async function generateResume(req, res, next) {
  try {
    const { jobDescription, experience, resumeType } = req.body;

    const result = await aiService.generateResumeContent({
      jobDescription,
      experience,
      resumeType,
    });

    logger.info('Resume generated successfully');

    res.status(200).json({
      success: true,
      data: result,
    });
  } catch (error) {
    next(error);
  }
}

/**
 * Optimize resume for ATS
 */
async function optimizeResume(req, res, next) {
  try {
    const { resumeContent, jobDescription } = req.body;

    // Extract keywords
    const keywords = await aiService.extractATSKeywords(jobDescription);

    // Optimize resume
    const optimizedContent = await aiService.optimizeResumeForATS(
      resumeContent,
      keywords,
    );

    logger.info('Resume optimized successfully');

    res.status(200).json({
      success: true,
      data: {
        optimizedContent,
        keywords,
      },
    });
  } catch (error) {
    next(error);
  }
}

module.exports = {
  generateResume,
  optimizeResume,
};
