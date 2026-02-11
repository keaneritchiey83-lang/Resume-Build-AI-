import { Request, Response } from 'express';
import { AuthRequest } from '../middleware/auth';
export declare const register: (req: Request, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const login: (req: Request, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const getProfile: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
//# sourceMappingURL=auth.controller.d.ts.map