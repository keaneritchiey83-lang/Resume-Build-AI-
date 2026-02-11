import { Response } from 'express';
import { AuthRequest } from '../middleware/auth';
export declare const analyzeResume: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const getATSScore: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
//# sourceMappingURL=ats.controller.d.ts.map