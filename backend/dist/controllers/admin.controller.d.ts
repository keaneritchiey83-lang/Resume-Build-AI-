import { Request, Response } from 'express';
export declare const getDashboardStats: (req: Request, res: Response) => Promise<void>;
export declare const getAllUsers: (req: Request, res: Response) => Promise<void>;
export declare const getUser: (req: Request, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const updateUser: (req: Request, res: Response) => Promise<void>;
export declare const deleteUser: (req: Request, res: Response) => Promise<void>;
export declare const getAllSubscriptions: (req: Request, res: Response) => Promise<void>;
//# sourceMappingURL=admin.controller.d.ts.map