import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import LandingPage from '../pages/LandingPage';

describe('LandingPage', () => {
  it('renders the landing page', () => {
    render(
      <BrowserRouter>
        <LandingPage />
      </BrowserRouter>
    );
    
    const elements = screen.getAllByText(/AI Resume Builder/i);
    expect(elements.length).toBeGreaterThan(0);
  });

  it('displays hero heading', () => {
    render(
      <BrowserRouter>
        <LandingPage />
      </BrowserRouter>
    );
    
    expect(screen.getByText(/Build ATS-Optimized Resumes/i)).toBeInTheDocument();
    expect(screen.getByText(/Powered by AI/i)).toBeInTheDocument();
  });

  it('has login and register buttons', () => {
    render(
      <BrowserRouter>
        <LandingPage />
      </BrowserRouter>
    );
    
    const loginLinks = screen.getAllByText(/Login/i);
    expect(loginLinks.length).toBeGreaterThan(0);
    
    const getStartedLinks = screen.getAllByText(/Get Started|Start Building Your Resume/i);
    expect(getStartedLinks.length).toBeGreaterThan(0);
  });
});
