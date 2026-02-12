import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import ResumePreview from '../components/ResumePreview';

describe('ResumePreview', () => {
  it('renders nothing when no resume is provided', () => {
    const { container } = render(<ResumePreview resume={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders resume content', () => {
    const mockResume = {
      content: 'Test resume content',
    };

    render(<ResumePreview resume={mockResume} />);
    expect(screen.getByText('Resume Preview')).toBeInTheDocument();
    expect(screen.getByText('Test resume content')).toBeInTheDocument();
  });

  it('renders ATS keywords when provided', () => {
    const mockResume = {
      content: 'Test resume content',
      keywords: ['JavaScript', 'React', 'Node.js'],
    };

    render(<ResumePreview resume={mockResume} />);
    expect(screen.getByText('ATS Keywords')).toBeInTheDocument();
    expect(screen.getByText('JavaScript')).toBeInTheDocument();
    expect(screen.getByText('React')).toBeInTheDocument();
    expect(screen.getByText('Node.js')).toBeInTheDocument();
  });
});
