"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
exports.getProfile = exports.login = exports.register = void 0;
const bcryptjs_1 = __importDefault(require("bcryptjs"));
const jsonwebtoken_1 = __importDefault(require("jsonwebtoken"));
const client_1 = require("@prisma/client");
const prisma = new client_1.PrismaClient();
const register = async (req, res) => {
    try {
        const { email, password, firstName, lastName } = req.body;
        // Validate input
        if (!email || !password) {
            return res.status(400).json({ message: 'Email and password are required' });
        }
        // Check if user exists
        const existingUser = await prisma.user.findUnique({ where: { email } });
        if (existingUser) {
            return res.status(400).json({ message: 'User already exists' });
        }
        // Hash password
        const hashedPassword = await bcryptjs_1.default.hash(password, 10);
        // Create user
        const user = await prisma.user.create({
            data: {
                email,
                password: hashedPassword,
                firstName,
                lastName,
                subscription: {
                    create: {
                        tier: 'FREE',
                        status: 'ACTIVE',
                    },
                },
            },
            include: {
                subscription: true,
            },
        });
        // Generate JWT
        const token = jsonwebtoken_1.default.sign({ userId: user.id, role: user.role }, process.env.JWT_SECRET || '', { expiresIn: process.env.JWT_EXPIRES_IN || '7d' });
        res.status(201).json({
            success: true,
            data: {
                user: {
                    id: user.id,
                    email: user.email,
                    firstName: user.firstName,
                    lastName: user.lastName,
                    role: user.role,
                    subscription: user.subscription,
                },
                token,
            },
        });
    }
    catch (error) {
        console.error('Registration error:', error);
        res.status(500).json({ message: 'Error creating user' });
    }
};
exports.register = register;
const login = async (req, res) => {
    try {
        const { email, password } = req.body;
        // Validate input
        if (!email || !password) {
            return res.status(400).json({ message: 'Email and password are required' });
        }
        // Find user
        const user = await prisma.user.findUnique({
            where: { email },
            include: { subscription: true },
        });
        if (!user) {
            return res.status(401).json({ message: 'Invalid credentials' });
        }
        // Verify password
        const isValidPassword = await bcryptjs_1.default.compare(password, user.password);
        if (!isValidPassword) {
            return res.status(401).json({ message: 'Invalid credentials' });
        }
        // Generate JWT
        const token = jsonwebtoken_1.default.sign({ userId: user.id, role: user.role }, process.env.JWT_SECRET || '', { expiresIn: process.env.JWT_EXPIRES_IN || '7d' });
        res.json({
            success: true,
            data: {
                user: {
                    id: user.id,
                    email: user.email,
                    firstName: user.firstName,
                    lastName: user.lastName,
                    role: user.role,
                    subscription: user.subscription,
                },
                token,
            },
        });
    }
    catch (error) {
        console.error('Login error:', error);
        res.status(500).json({ message: 'Error logging in' });
    }
};
exports.login = login;
const getProfile = async (req, res) => {
    try {
        const user = await prisma.user.findUnique({
            where: { id: req.userId },
            include: { subscription: true },
        });
        if (!user) {
            return res.status(404).json({ message: 'User not found' });
        }
        res.json({ success: true, data: user });
    }
    catch (error) {
        console.error('Get profile error:', error);
        res.status(500).json({ message: 'Error fetching profile' });
    }
};
exports.getProfile = getProfile;
//# sourceMappingURL=auth.controller.js.map