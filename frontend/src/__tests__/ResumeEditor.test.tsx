import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ResumeEditorPage from '../pages/ResumeEditorPage';

// Mock react-router-dom
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ id: undefined }),
    useNavigate: () => vi.fn(),
  };
});

// Mock the API
vi.mock('../services/api', () => ({
  resumeAPI: {
    getOne: vi.fn(() => Promise.resolve({ 
      data: { 
        data: { 
          id: '1', 
          title: 'Test Resume',
          content: { personalInfo: {}, summary: '', experience: [], education: [], skills: [] }
        } 
      } 
    })),
    create: vi.fn(),
    update: vi.fn(),
  },
}));

describe('ResumeEditorPage', () => {
  it('renders the resume editor', async () => {
    render(
      <BrowserRouter>
        <ResumeEditorPage />
      </BrowserRouter>
    );
    
    await waitFor(() => {
      expect(screen.getByText(/Personal Information/i)).toBeInTheDocument();
    });
  });

  it('displays save button', async () => {
    render(
      <BrowserRouter>
        <ResumeEditorPage />
      </BrowserRouter>
    );
    
    await waitFor(() => {
      expect(screen.getByText(/Save/i)).toBeInTheDocument();
    });
  });
});
