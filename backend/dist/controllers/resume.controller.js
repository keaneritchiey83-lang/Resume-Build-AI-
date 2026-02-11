"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.deleteResume = exports.updateResume = exports.getResume = exports.getResumes = exports.createResume = void 0;
const client_1 = require("@prisma/client");
const prisma = new client_1.PrismaClient();
const createResume = async (req, res) => {
    try {
        const { title, template, content } = req.body;
        const resume = await prisma.resume.create({
            data: {
                userId: req.userId,
                title,
                template: template || 'modern',
                content,
            },
        });
        res.status(201).json({ success: true, data: resume });
    }
    catch (error) {
        console.error('Create resume error:', error);
        res.status(500).json({ message: 'Error creating resume' });
    }
};
exports.createResume = createResume;
const getResumes = async (req, res) => {
    try {
        const resumes = await prisma.resume.findMany({
            where: { userId: req.userId },
            orderBy: { updatedAt: 'desc' },
            include: {
                atsAnalyses: {
                    take: 1,
                    orderBy: { createdAt: 'desc' },
                },
            },
        });
        res.json({ success: true, data: resumes });
    }
    catch (error) {
        console.error('Get resumes error:', error);
        res.status(500).json({ message: 'Error fetching resumes' });
    }
};
exports.getResumes = getResumes;
const getResume = async (req, res) => {
    try {
        const { id } = req.params;
        const resume = await prisma.resume.findFirst({
            where: {
                id,
                userId: req.userId,
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
    }
    catch (error) {
        console.error('Get resume error:', error);
        res.status(500).json({ message: 'Error fetching resume' });
    }
};
exports.getResume = getResume;
const updateResume = async (req, res) => {
    try {
        const { id } = req.params;
        const { title, template, content, atsScore } = req.body;
        const resume = await prisma.resume.findFirst({
            where: {
                id,
                userId: req.userId,
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
    }
    catch (error) {
        console.error('Update resume error:', error);
        res.status(500).json({ message: 'Error updating resume' });
    }
};
exports.updateResume = updateResume;
const deleteResume = async (req, res) => {
    try {
        const { id } = req.params;
        const resume = await prisma.resume.findFirst({
            where: {
                id,
                userId: req.userId,
            },
        });
        if (!resume) {
            return res.status(404).json({ message: 'Resume not found' });
        }
        await prisma.resume.delete({ where: { id } });
        res.json({ success: true, message: 'Resume deleted successfully' });
    }
    catch (error) {
        console.error('Delete resume error:', error);
        res.status(500).json({ message: 'Error deleting resume' });
    }
};
exports.deleteResume = deleteResume;
//# sourceMappingURL=resume.controller.js.map