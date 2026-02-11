"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const express_1 = __importDefault(require("express"));
const cors_1 = __importDefault(require("cors"));
const dotenv_1 = __importDefault(require("dotenv"));
const auth_routes_1 = __importDefault(require("./routes/auth.routes"));
const resume_routes_1 = __importDefault(require("./routes/resume.routes"));
const subscription_routes_1 = __importDefault(require("./routes/subscription.routes"));
const ats_routes_1 = __importDefault(require("./routes/ats.routes"));
const admin_routes_1 = __importDefault(require("./routes/admin.routes"));
const team_routes_1 = __importDefault(require("./routes/team.routes"));
const prediction_routes_1 = __importDefault(require("./routes/prediction.routes"));
const errorHandler_1 = require("./middleware/errorHandler");
const rateLimit_1 = require("./middleware/rateLimit");
dotenv_1.default.config();
const app = (0, express_1.default)();
const PORT = process.env.PORT || 5000;
// Global rate limiting for all routes
// Limits requests per IP address to prevent abuse
app.use((0, rateLimit_1.rateLimit)({
    windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '900000'), // 15 minutes
    maxRequests: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS || '100'),
}));
// Middleware
app.use((0, cors_1.default)({
    origin: process.env.CORS_ORIGIN || 'http://localhost:3000',
    credentials: true,
}));
app.use(express_1.default.json());
app.use(express_1.default.urlencoded({ extended: true }));
// Health check
app.get('/health', (req, res) => {
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
});
// API Routes
app.use('/api/auth', auth_routes_1.default);
app.use('/api/resumes', resume_routes_1.default);
app.use('/api/subscriptions', subscription_routes_1.default);
app.use('/api/ats', ats_routes_1.default);
app.use('/api/admin', admin_routes_1.default);
app.use('/api/teams', team_routes_1.default);
app.use('/api/predictions', prediction_routes_1.default);
// Error handling middleware
app.use(errorHandler_1.errorHandler);
// Start server
app.listen(PORT, () => {
    console.log(`🚀 Server running on port ${PORT}`);
    console.log(`📊 Environment: ${process.env.NODE_ENV}`);
});
exports.default = app;
//# sourceMappingURL=index.js.map