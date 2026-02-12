import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import App from '../App';

// Mock the auth store
vi.mock('../store/authStore', () => ({
  useAuthStore: () => ({
    loadUser: vi.fn(),
    isLoading: false,
  }),
}));

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    expect(document.body).toBeTruthy();
  });

  it('renders landing page by default', () => {
    render(<App />);
    // Check for landing page content
    const elements = screen.getAllByText(/AI Resume Builder/i);
    expect(elements.length).toBeGreaterThan(0);
  });
});
