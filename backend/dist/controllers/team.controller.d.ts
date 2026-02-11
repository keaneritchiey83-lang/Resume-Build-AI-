import { Response } from 'express';
import { AuthRequest } from '../middleware/auth';
export declare const createTeam: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const getTeams: (req: AuthRequest, res: Response) => Promise<void>;
export declare const getTeam: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const updateTeam: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const deleteTeam: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const addMember: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const removeMember: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
export declare const getMembers: (req: AuthRequest, res: Response) => Promise<Response<any, Record<string, any>> | undefined>;
//# sourceMappingURL=team.controller.d.ts.map