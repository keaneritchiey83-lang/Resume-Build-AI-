import { Response } from 'express';
import { AuthRequest } from '../middleware/auth';
export declare const createResume: (req: AuthRequest, res: Response) => Promise<void>;
export declare const getResumes: (req: AuthRequest, res: Response) => Promise<void>;
export declare const getResume: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const updateResume: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const deleteResume: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
//# sourceMappingURL=resume.controller.d.ts.map