import { Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { AuthRequest } from '../middleware/auth';
import { ATSEngine } from '../services/ats.service';

const prisma = new PrismaClient();

export const analyzeResume = async (req: AuthRequest, res: Response) => {
  try {
    const { resumeId, jobDescription } = req.body;

    if (!resumeId || !jobDescription) {
      return res.status(400).json({
        message: 'Resume ID and job description are required',
      });
    }

    // Get resume
    const resume = await prisma.resume.findFirst({
      where: {
        id: resumeId,
        userId: req.userId!,
      },
    });

    if (!resume) {
      return res.status(404).json({ message: 'Resume not found' });
    }

    // Extract text from resume content
    const resumeText = extractTextFromContent(resume.content);

    // Analyze with ATS engine
    const analysis = ATSEngine.analyzeResume(resumeText, jobDescription);

    // Save analysis
    const atsAnalysis = await prisma.aTSAnalysis.create({
      data: {
        resumeId,
        jobDescription,
        overallScore: analysis.overallScore,
        keywordScore: analysis.keywordScore,
        semanticScore: analysis.semanticScore,
        impactScore: analysis.impactScore,
        suggestions: analysis.suggestions,
      },
    });

    // Update resume with latest score
    await prisma.resume.update({
      where: { id: resumeId },
      data: {
        atsScore: analysis.overallScore,
        keywordMatches: {
          matched: analysis.matchedKeywords,
          missing: analysis.missingKeywords,
        },
        impactScore: analysis.impactScore,
      },
    });

    res.json({
      success: true,
      data: {
        ...analysis,
        analysisId: atsAnalysis.id,
      },
    });
  } catch (error) {
    console.error('ATS analysis error:', error);
    res.status(500).json({ message: 'Error analyzing resume' });
  }
};

export const getATSScore = async (req: AuthRequest, res: Response) => {
  try {
    const { resumeId } = req.params;

    const resume = await prisma.resume.findFirst({
      where: {
        id: resumeId,
        userId: req.userId!,
      },
      include: {
        atsAnalyses: {
          orderBy: { createdAt: 'desc' },
          take: 5,
        },
      },
    });

    if (!resume) {
      return res.status(404).json({ message: 'Resume not found' });
    }

    res.json({ success: true, data: resume });
  } catch (error) {
    console.error('Get ATS score error:', error);
    res.status(500).json({ message: 'Error fetching ATS score' });
  }
};

// Helper function to extract text from resume content
function extractTextFromContent(content: any): string {
  if (typeof content === 'string') {
    return content;
  }

  let text = '';
  
  // Handle structured content
  if (content.personalInfo) {
    text += `${content.personalInfo.name || ''} ${content.personalInfo.title || ''}\n`;
  }

  if (content.summary) {
    text += `${content.summary}\n`;
  }

  if (content.experience && Array.isArray(content.experience)) {
    content.experience.forEach((exp: any) => {
      text += `${exp.title || ''} ${exp.company || ''}\n`;
      if (exp.description) text += `${exp.description}\n`;
      if (exp.achievements && Array.isArray(exp.achievements)) {
        exp.achievements.forEach((achievement: string) => {
          text += `• ${achievement}\n`;
        });
      }
    });
  }

  if (content.education && Array.isArray(content.education)) {
    content.education.forEach((edu: any) => {
      text += `${edu.degree || ''} ${edu.school || ''}\n`;
    });
  }

  if (content.skills && Array.isArray(content.skills)) {
    text += content.skills.join(', ') + '\n';
  }

  return text;
}
