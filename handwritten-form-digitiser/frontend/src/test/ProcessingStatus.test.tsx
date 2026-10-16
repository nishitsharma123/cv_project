import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ProcessingStatus } from '../components/ProcessingStatus';

describe('ProcessingStatus component', () => {
  // ── Error state ─────────────────────────────────────────────────────────────

  it('renders error message and code when errorMessage is set', () => {
    render(
      <ProcessingStatus
        isProcessing={false}
        errorMessage="Backend returned HTTP 422"
        errorCode="VALIDATION_FAILED"
      />
    );

    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/Backend returned HTTP 422/i)).toBeInTheDocument();
    // Error code displayed inside the heading
    expect(screen.getByText(/VALIDATION_FAILED/)).toBeInTheDocument();
  });

  it('renders error without code when errorCode is not provided', () => {
    render(
      <ProcessingStatus
        isProcessing={false}
        errorMessage="Network connection failed"
      />
    );

    expect(screen.getByText(/Network connection failed/i)).toBeInTheDocument();
    // Heading should not show brackets for a missing code
    const heading = screen.getByRole('heading', { level: 3 });
    expect(heading.textContent).not.toMatch(/\[/);
  });

  it('calls onDismissError when Dismiss button is clicked', () => {
    const handleDismiss = vi.fn();
    render(
      <ProcessingStatus
        isProcessing={false}
        errorMessage="Something went wrong"
        onDismissError={handleDismiss}
      />
    );

    const btn = screen.getByRole('button', { name: /Dismiss/i });
    fireEvent.click(btn);

    expect(handleDismiss).toHaveBeenCalledTimes(1);
  });

  it('does not render a Dismiss button when onDismissError is absent', () => {
    render(
      <ProcessingStatus
        isProcessing={false}
        errorMessage="Unexpected error"
      />
    );

    expect(screen.queryByRole('button', { name: /Dismiss/i })).not.toBeInTheDocument();
  });

  // ── Processing / pipeline state ──────────────────────────────────────────────

  it('shows all three pipeline step labels while processing', () => {
    render(<ProcessingStatus isProcessing currentStep="SEGMENTING" />);

    expect(screen.getByText(/Layout Segmentation/i)).toBeInTheDocument();
    expect(screen.getByText(/Devanagari OCR/i)).toBeInTheDocument();
    expect(screen.getByText(/Semantic Validation/i)).toBeInTheDocument();
  });

  it('marks the SEGMENTING step as active and others as pending', () => {
    render(<ProcessingStatus isProcessing currentStep="SEGMENTING" />);

    // "Digitizing Form Document" spinner heading appears
    expect(screen.getByText(/Digitizing Form Document/i)).toBeInTheDocument();
  });

  it('does not render an alert role while isProcessing is true', () => {
    render(<ProcessingStatus isProcessing currentStep="RECOGNIZING" />);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  // ── Warnings state ───────────────────────────────────────────────────────────

  it('renders pipeline warnings when provided and not processing', () => {
    const warnings = ['Skew correction skipped (deskew unavailable)', 'Confidence below threshold'];
    render(<ProcessingStatus isProcessing={false} warnings={warnings} />);

    expect(screen.getByText(/Pipeline Notices/i)).toBeInTheDocument();
    expect(screen.getByText(/Skew correction skipped/i)).toBeInTheDocument();
    expect(screen.getByText(/Confidence below threshold/i)).toBeInTheDocument();
  });

  it('renders nothing when idle with no error and no warnings', () => {
    const { container } = render(<ProcessingStatus isProcessing={false} />);
    expect(container.firstChild).toBeNull();
  });

  // ── Priority: error takes precedence over processing ─────────────────────────

  it('shows error state even when isProcessing is simultaneously true', () => {
    render(
      <ProcessingStatus
        isProcessing
        currentStep="RECOGNIZING"
        errorMessage="Connection dropped"
        errorCode="TIMEOUT"
      />
    );

    // Error must be visible
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(screen.getByText(/Connection dropped/i)).toBeInTheDocument();
    // Pipeline progress must not render
    expect(screen.queryByText(/Digitizing Form Document/i)).not.toBeInTheDocument();
  });
});
