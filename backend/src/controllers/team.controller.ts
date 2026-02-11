import { Response } from 'express';
import { PrismaClient } from '@prisma/client';
import { AuthRequest } from '../middleware/auth';

const prisma = new PrismaClient();

export const createTeam = async (req: AuthRequest, res: Response) => {
  try {
    const { name, maxMembers } = req.body;

    if (!name) {
      return res.status(400).json({ message: 'Team name is required' });
    }

    const team = await prisma.team.create({
      data: {
        name,
        ownerId: req.userId!,
        maxMembers: maxMembers || 10,
        subscriptionTier: 'PRO',
      },
    });

    res.status(201).json({ success: true, data: team });
  } catch (error) {
    console.error('Create team error:', error);
    res.status(500).json({ message: 'Error creating team' });
  }
};

export const getTeams = async (req: AuthRequest, res: Response) => {
  try {
    const teams = await prisma.team.findMany({
      where: {
        OR: [
          { ownerId: req.userId! },
          { members: { some: { userId: req.userId! } } },
        ],
      },
      include: {
        members: {
          include: {
            user: {
              select: {
                id: true,
                email: true,
                firstName: true,
                lastName: true,
              },
            },
          },
        },
        owner: {
          select: {
            id: true,
            email: true,
            firstName: true,
            lastName: true,
          },
        },
      },
    });

    res.json({ success: true, data: teams });
  } catch (error) {
    console.error('Get teams error:', error);
    res.status(500).json({ message: 'Error fetching teams' });
  }
};

export const getTeam = async (req: AuthRequest, res: Response) => {
  try {
    const { id } = req.params;

    const team = await prisma.team.findFirst({
      where: {
        id,
        OR: [
          { ownerId: req.userId! },
          { members: { some: { userId: req.userId! } } },
        ],
      },
      include: {
        members: {
          include: {
            user: {
              select: {
                id: true,
                email: true,
                firstName: true,
                lastName: true,
              },
            },
          },
        },
        owner: {
          select: {
            id: true,
            email: true,
            firstName: true,
            lastName: true,
          },
        },
      },
    });

    if (!team) {
      return res.status(404).json({ message: 'Team not found' });
    }

    res.json({ success: true, data: team });
  } catch (error) {
    console.error('Get team error:', error);
    res.status(500).json({ message: 'Error fetching team' });
  }
};

export const updateTeam = async (req: AuthRequest, res: Response) => {
  try {
    const { id } = req.params;
    const { name, maxMembers } = req.body;

    const team = await prisma.team.findFirst({
      where: { id, ownerId: req.userId! },
    });

    if (!team) {
      return res.status(404).json({ message: 'Team not found or unauthorized' });
    }

    const updatedTeam = await prisma.team.update({
      where: { id },
      data: {
        ...(name && { name }),
        ...(maxMembers && { maxMembers }),
      },
    });

    res.json({ success: true, data: updatedTeam });
  } catch (error) {
    console.error('Update team error:', error);
    res.status(500).json({ message: 'Error updating team' });
  }
};

export const deleteTeam = async (req: AuthRequest, res: Response) => {
  try {
    const { id } = req.params;

    const team = await prisma.team.findFirst({
      where: { id, ownerId: req.userId! },
    });

    if (!team) {
      return res.status(404).json({ message: 'Team not found or unauthorized' });
    }

    await prisma.team.delete({ where: { id } });

    res.json({ success: true, message: 'Team deleted successfully' });
  } catch (error) {
    console.error('Delete team error:', error);
    res.status(500).json({ message: 'Error deleting team' });
  }
};

export const addMember = async (req: AuthRequest, res: Response) => {
  try {
    const { id } = req.params;
    const { email, role } = req.body;

    const team = await prisma.team.findFirst({
      where: { id, ownerId: req.userId! },
      include: { members: true },
    });

    if (!team) {
      return res.status(404).json({ message: 'Team not found or unauthorized' });
    }

    if (team.members.length >= team.maxMembers) {
      return res.status(400).json({ message: 'Team has reached maximum members' });
    }

    const user = await prisma.user.findUnique({ where: { email } });

    if (!user) {
      return res.status(404).json({ message: 'User not found' });
    }

    const member = await prisma.teamMember.create({
      data: {
        teamId: id,
        userId: user.id,
        role: role || 'member',
      },
      include: {
        user: {
          select: {
            id: true,
            email: true,
            firstName: true,
            lastName: true,
          },
        },
      },
    });

    res.status(201).json({ success: true, data: member });
  } catch (error: any) {
    if (error.code === 'P2002') {
      return res.status(400).json({ message: 'User is already a team member' });
    }
    console.error('Add member error:', error);
    res.status(500).json({ message: 'Error adding team member' });
  }
};

export const removeMember = async (req: AuthRequest, res: Response) => {
  try {
    const { id, userId } = req.params;

    const team = await prisma.team.findFirst({
      where: { id, ownerId: req.userId! },
    });

    if (!team) {
      return res.status(404).json({ message: 'Team not found or unauthorized' });
    }

    await prisma.teamMember.delete({
      where: {
        teamId_userId: {
          teamId: id,
          userId,
        },
      },
    });

    res.json({ success: true, message: 'Member removed successfully' });
  } catch (error) {
    console.error('Remove member error:', error);
    res.status(500).json({ message: 'Error removing team member' });
  }
};

export const getMembers = async (req: AuthRequest, res: Response) => {
  try {
    const { id } = req.params;

    const team = await prisma.team.findFirst({
      where: {
        id,
        OR: [
          { ownerId: req.userId! },
          { members: { some: { userId: req.userId! } } },
        ],
      },
    });

    if (!team) {
      return res.status(404).json({ message: 'Team not found' });
    }

    const members = await prisma.teamMember.findMany({
      where: { teamId: id },
      include: {
        user: {
          select: {
            id: true,
            email: true,
            firstName: true,
            lastName: true,
          },
        },
      },
    });

    res.json({ success: true, data: members });
  } catch (error) {
    console.error('Get members error:', error);
    res.status(500).json({ message: 'Error fetching team members' });
  }
};
