const aiService = require('../services/aiService');
const logger = require('../config/logger');

/**
 * Generate interview questions
 */
async function prepareInterview(req, res, next) {
  try {
    const { jobDescription, interviewType } = req.body;

    const questions = await aiService.generateInterviewQuestions({
      jobDescription,
      interviewType,
    });

    logger.info(`Generated ${questions.length} ${interviewType} interview questions`);

    res.status(200).json({
      success: true,
      data: {
        questions,
        interviewType,
      },
    });
  } catch (error) {
    next(error);
  }
}

module.exports = {
  prepareInterview,
};
