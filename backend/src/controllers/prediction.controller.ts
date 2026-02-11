import { Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { AuthRequest } from '../middleware/auth';
import { CallbackPredictor } from '../services/prediction.service';

const prisma = new PrismaClient();

export const predictCallback = async (req: AuthRequest, res: Response) => {
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
      include: {
        atsAnalyses: {
          orderBy: { createdAt: 'desc' },
          take: 1,
        },
      },
    });

    if (!resume) {
      return res.status(404).json({ message: 'Resume not found' });
    }

    // Get prediction
    const prediction = CallbackPredictor.predict(resume, jobDescription);

    // Save prediction
    await prisma.callbackPrediction.create({
      data: {
        resumeData: resume.content as any,
        jobDescription,
        predictionScore: prediction.score,
        confidence: prediction.confidence,
        factors: prediction.factors as any,
      },
    });

    res.json({ success: true, data: prediction });
  } catch (error) {
    console.error('Prediction error:', error);
    res.status(500).json({ message: 'Error generating prediction' });
  }
};
