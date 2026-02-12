const aiService = require('../services/aiService');
const logger = require('../config/logger');

/**
 * Analyze skill gap
 */
async function analyzeSkillGap(req, res, next) {
  try {
    const { currentSkills, jobDescription } = req.body;

    const analysis = await aiService.analyzeSkillGap(
      currentSkills,
      jobDescription,
    );

    logger.info('Skill gap analysis completed');

    res.status(200).json({
      success: true,
      data: analysis,
    });
  } catch (error) {
    next(error);
  }
}

module.exports = {
  analyzeSkillGap,
};
