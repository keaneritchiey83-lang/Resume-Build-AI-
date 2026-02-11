import { Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { AuthRequest } from '../middleware/auth';

const prisma = new PrismaClient();

export const createResume = async (req: AuthRequest, res: Response) => {
  try {
    const { title, template, content } = req.body;

    const resume = await prisma.resume.create({
      data: {
        userId: req.userId!,
        title,
        template: template || 'modern',
        content,
      },
    });

    res.status(201).json({ success: true, data: resume });
  } catch (error) {
    console.error('Create resume error:', error);
    res.status(500).json({ message: 'Error creating resume' });
  }
};

export const getResumes = async (req: AuthRequest, res: Response) => {
  try {
    const resumes = await prisma.resume.findMany({
      where: { userId: req.userId! },
      orderBy: { updatedAt: 'desc' },
      include: {
        atsAnalyses: {
          take: 1,
          orderBy: { createdAt: 'desc' },
        },
      },
    });

    res.json({ success: true, data: resumes });
  } catch (error) {
    console.error('Get resumes error:', error);
    res.status(500).json({ message: 'Error fetching resumes' });
  }
};

export const getResume = async (req: AuthRequest, res: Response) => {
  try {
    const { id } = req.params;

    const resume = await prisma.resume.findFirst({
      where: {
        id,
        userId: req.userId!,
      },
      include: {
        atsAnalyses: {
          orderBy: { createdAt: 'desc' },
        },
      },
    });

    if (!resume) {
      return res.status(404).json({ message: 'Resume not found' });
    }

    res.json({ success: true, data: resume });
  } catch (error) {
    console.error('Get resume error:', error);
    res.status(500).json({ message: 'Error fetching resume' });
  }
};

export const updateResume = async (req: AuthRequest, res: Response) => {
  try {
    const { id } = req.params;
    const { title, template, content, atsScore } = req.body;

    const resume = await prisma.resume.findFirst({
      where: {
        id,
        userId: req.userId!,
      },
    });

    if (!resume) {
      return res.status(404).json({ message: 'Resume not found' });
    }

    const updatedResume = await prisma.resume.update({
      where: { id },
      data: {
        ...(title && { title }),
        ...(template && { template }),
        ...(content && { content }),
        ...(atsScore !== undefined && { atsScore }),
      },
    });

    res.json({ success: true, data: updatedResume });
  } catch (error) {
    console.error('Update resume error:', error);
    res.status(500).json({ message: 'Error updating resume' });
  }
};

export const deleteResume = async (req: AuthRequest, res: Response) => {
  try {
    const { id } = req.params;

    const resume = await prisma.resume.findFirst({
      where: {
        id,
        userId: req.userId!,
      },
    });

    if (!resume) {
      return res.status(404).json({ message: 'Resume not found' });
    }

    await prisma.resume.delete({ where: { id } });

    res.json({ success: true, message: 'Resume deleted successfully' });
  } catch (error) {
    console.error('Delete resume error:', error);
    res.status(500).json({ message: 'Error deleting resume' });
  }
};
