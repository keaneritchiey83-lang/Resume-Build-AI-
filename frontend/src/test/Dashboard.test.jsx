import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Dashboard from '../pages/Dashboard';

describe('Dashboard', () => {
  it('renders dashboard with statistics', () => {
    render(<Dashboard />);

    expect(screen.getByText('Application Tracking Dashboard')).toBeInTheDocument();
    expect(screen.getByText('Resumes Created')).toBeInTheDocument();
    expect(screen.getByText('Interviews Prepared')).toBeInTheDocument();
    expect(screen.getByText('Applications')).toBeInTheDocument();
    expect(screen.getByText('Success Rate')).toBeInTheDocument();
  });

  it('shows no activity message', () => {
    render(<Dashboard />);
    expect(screen.getByText(/No recent activity yet/i)).toBeInTheDocument();
  });
});
