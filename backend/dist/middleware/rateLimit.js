"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.rateLimit = void 0;
const store = {};
const rateLimit = (options) => {
    return (req, res, next) => {
        const key = req.ip || req.socket.remoteAddress || 'unknown';
        const now = Date.now();
        // Clean up expired entries
        if (store[key] && now > store[key].resetTime) {
            delete store[key];
        }
        // Initialize or increment
        if (!store[key]) {
            store[key] = {
                count: 1,
                resetTime: now + options.windowMs,
            };
            return next();
        }
        store[key].count++;
        // Check if limit exceeded
        if (store[key].count > options.maxRequests) {
            return res.status(429).json({
                success: false,
                message: 'Too many requests, please try again later.',
            });
        }
        next();
    };
};
exports.rateLimit = rateLimit;
// Cleanup old entries every hour (only in non-test environment)
if (process.env.NODE_ENV !== 'test') {
    setInterval(() => {
        const now = Date.now();
        Object.keys(store).forEach((key) => {
            if (now > store[key].resetTime) {
                delete store[key];
            }
        });
    }, 3600000);
}
//# sourceMappingURL=rateLimit.js.map