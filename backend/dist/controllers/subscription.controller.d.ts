import { Request, Response } from 'express';
import { AuthRequest } from '../middleware/auth';
export declare const createCheckoutSession: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const handleWebhook: (req: Request, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const getSubscription: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const cancelSubscription: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
//# sourceMappingURL=subscription.controller.d.ts.map