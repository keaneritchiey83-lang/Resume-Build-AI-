"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.predictCallback = void 0;
const client_1 = require("@prisma/client");
const prediction_service_1 = require("../services/prediction.service");
const prisma = new client_1.PrismaClient();
const predictCallback = async (req, res) => {
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
                userId: req.userId,
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
        const prediction = prediction_service_1.CallbackPredictor.predict(resume, jobDescription);
        // Save prediction
        await prisma.callbackPrediction.create({
            data: {
                resumeData: resume.content,
                jobDescription,
                predictionScore: prediction.score,
                confidence: prediction.confidence,
                factors: prediction.factors,
            },
        });
        res.json({ success: true, data: prediction });
    }
    catch (error) {
        console.error('Prediction error:', error);
        res.status(500).json({ message: 'Error generating prediction' });
    }
};
exports.predictCallback = predictCallback;
//# sourceMappingURL=prediction.controller.js.map