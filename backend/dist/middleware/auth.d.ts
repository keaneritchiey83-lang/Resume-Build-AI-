import { Request, Response, NextFunction } from 'express';
export interface AuthRequest extends Request {
    userId?: string;
    userRole?: string;
}
export declare const authenticate: (req: AuthRequest, res: Response, next: NextFunction) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const requireAdmin: (req: AuthRequest, res: Response, next: NextFunction) => Response<any, Record<string, any>> | undefined;
//# sourceMappingURL=auth.d.ts.map