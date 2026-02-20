import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import LandingPage from '../pages/LandingPage';
import LoginPage from '../pages/LoginPage';

// Mock the auth store
vi.mock('../store/authStore', () => ({
  useAuthStore: () => ({
    login: vi.fn(),
    isLoading: false,
  }),
}));

describe('Navigation', () => {
  it('renders landing page at root path', () => {
    render(
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
        </Routes>
      </MemoryRouter>
    );
    
    const elements = screen.getAllByText(/AI Resume Builder/i);
    expect(elements.length).toBeGreaterThan(0);
    expect(screen.getByText(/Build ATS-Optimized Resumes/i)).toBeInTheDocument();
  });

  it('renders login page at /login path', () => {
    render(
      <MemoryRouter initialEntries={['/login']}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
        </Routes>
      </MemoryRouter>
    );
    
    // Check if we're on login page
    expect(screen.getByPlaceholderText(/you@example.com/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/••••••••/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Sign in/i })).toBeInTheDocument();
  });
});
