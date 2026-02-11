import { Request, Response, NextFunction } from 'express';
export declare const rateLimit: (options: {
    windowMs: number;
    maxRequests: number;
}) => (req: Request, res: Response, next: NextFunction) => void | Response<any, Record<string, any>>;
//# sourceMappingURL=rateLimit.d.ts.map