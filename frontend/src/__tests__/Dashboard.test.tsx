import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import DashboardPage from '../pages/DashboardPage';

// Mock the auth store
vi.mock('../store/authStore', () => ({
  useAuthStore: () => ({
    user: { firstName: 'Test', email: 'test@example.com' },
  }),
}));

// Mock the API
vi.mock('../services/api', () => ({
  resumeAPI: {
    getAll: vi.fn(() => Promise.resolve({ data: { data: [] } })),
  },
}));

describe('DashboardPage', () => {
  it('renders the dashboard', async () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>
    );
    
    await waitFor(() => {
      expect(screen.getByText(/Welcome back, Test/i)).toBeInTheDocument();
    });
  });

  it('displays overview message', async () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>
    );
    
    await waitFor(() => {
      expect(screen.getByText(/Here's an overview of your resume building progress/i)).toBeInTheDocument();
    });
  });

  it('displays total resumes stat', async () => {
    render(
      <BrowserRouter>
        <DashboardPage />
      </BrowserRouter>
    );
    
    await waitFor(() => {
      expect(screen.getByText(/Total Resumes/i)).toBeInTheDocument();
    });
  });
});
