import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import Navigation from '../components/Navigation';

describe('Navigation', () => {
  it('renders navigation links', () => {
    render(
      <BrowserRouter>
        <Navigation />
      </BrowserRouter>
    );

    expect(screen.getByText('Resume Build AI')).toBeInTheDocument();
    expect(screen.getByText('Resume Builder')).toBeInTheDocument();
    expect(screen.getByText('Interview Prep')).toBeInTheDocument();
    expect(screen.getByText('Dashboard')).toBeInTheDocument();
  });
});
