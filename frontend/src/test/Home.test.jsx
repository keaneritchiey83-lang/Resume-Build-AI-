import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import Home from '../pages/Home';

describe('Home', () => {
  it('renders home page with hero section', () => {
    render(
      <BrowserRouter>
        <Home />
      </BrowserRouter>
    );

    expect(screen.getByText('Resume Build AI')).toBeInTheDocument();
    expect(screen.getByText(/AI-powered resume and interview preparation platform/i)).toBeInTheDocument();
    expect(screen.getByText('Build Resume')).toBeInTheDocument();
    expect(screen.getByText('Interview Prep')).toBeInTheDocument();
  });

  it('renders features section', () => {
    render(
      <BrowserRouter>
        <Home />
      </BrowserRouter>
    );

    expect(screen.getByText('Core Capabilities')).toBeInTheDocument();
    expect(screen.getByText(/Resume Generation/i)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /Interview Preparation/i, level: 3 })).toBeInTheDocument();
    expect(screen.getByText(/Career Strategy/i)).toBeInTheDocument();
  });
});
