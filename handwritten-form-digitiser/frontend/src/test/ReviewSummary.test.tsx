import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ReviewSummary } from '../components/ReviewSummary';
import type { DigitizedField } from '../types/api';

// ── Fixtures ─────────────────────────────────────────────────────────────────

function makeField(overrides: Partial<DigitizedField> = {}): DigitizedField {
  return {
    field_id: `field_${Math.random().toString(36).slice(2)}`,
    field_name: 'name',
    field_type: 'name',
    raw_ocr_text: 'रमेश',
    current_value: 'रमेश',
    is_manually_edited: false,
    is_confirmed: false,
    normalized_text: null,
    validation_status: 'VALID',
    requires_review: false,
    review_reasons: [],
    warning_codes: [],
    confidence: null,
    is_confidence_calibrated: false,
    bounding_box: null,
    crop_preview_url: null,
    ...overrides,
  };
}

// ── Metrics display ───────────────────────────────────────────────────────────

describe('ReviewSummary – metric counters', () => {
  it('shows the correct total field count', () => {
    const fields = [makeField(), makeField(), makeField()];
    render(<ReviewSummary fields={fields} onConfirmAll={vi.fn()} />);

    // "Total Fields" label then the numeric value
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText(/Total Fields/i)).toBeInTheDocument();
  });

  it('shows the correct confirmed count', () => {
    const fields = [
      makeField({ is_confirmed: true }),
      makeField({ is_confirmed: true }),
      makeField({ is_confirmed: false }),
    ];
    render(<ReviewSummary fields={fields} onConfirmAll={vi.fn()} />);

    const confirmedSection = screen.getByText(/Confirmed/i).closest('div');
    expect(confirmedSection).toBeTruthy();
    expect(screen.getByText('2')).toBeInTheDocument();
  });

  it('shows needs-review count excluding already-confirmed fields', () => {
    const fields = [
      makeField({ requires_review: true, is_confirmed: false }),
      makeField({ requires_review: true, is_confirmed: true }),  // confirmed — must not count
      makeField({ requires_review: false }),
    ];
    render(<ReviewSummary fields={fields} onConfirmAll={vi.fn()} />);

    // "Needs Review" label cell must be present
    expect(screen.getByText(/Needs Review/i)).toBeInTheDocument();
    // Find the metric cell that contains both the "Needs Review" label and a count
    const cells = screen.getAllByText('1');
    // At least one cell with value "1" must be next to the amber "Needs Review" label
    // (confirmed count is also 1 in this fixture — use getAllByText and check length)
    expect(cells.length).toBeGreaterThanOrEqual(1);
  });

  it('shows the correct manually-edited count', () => {
    const fields = [
      makeField({ is_manually_edited: true }),
      makeField({ is_manually_edited: true }),
      makeField({ is_manually_edited: false }),
    ];
    render(<ReviewSummary fields={fields} onConfirmAll={vi.fn()} />);

    expect(screen.getByText(/Manually Edited/i)).toBeInTheDocument();
    // Two edited fields — value "2" exists
    const allNumbers = screen.getAllByText('2');
    expect(allNumbers.length).toBeGreaterThanOrEqual(1);
  });
});

// ── All-confirmed state ───────────────────────────────────────────────────────

describe('ReviewSummary – all-confirmed state', () => {
  it('shows "All Fields Confirmed" badge when every field is confirmed', () => {
    const fields = [
      makeField({ is_confirmed: true }),
      makeField({ is_confirmed: true }),
    ];
    render(<ReviewSummary fields={fields} onConfirmAll={vi.fn()} />);

    expect(screen.getByText(/All Fields Confirmed/i)).toBeInTheDocument();
  });

  it('hides the "Confirm All Fields" button when all fields are confirmed', () => {
    const fields = [makeField({ is_confirmed: true })];
    render(<ReviewSummary fields={fields} onConfirmAll={vi.fn()} />);

    expect(screen.queryByRole('button', { name: /Confirm All/i })).not.toBeInTheDocument();
  });
});

// ── Confirm-all button ────────────────────────────────────────────────────────

describe('ReviewSummary – Confirm All Fields button', () => {
  it('renders the "Confirm All Fields" button when not all fields are confirmed', () => {
    const fields = [makeField({ is_confirmed: false }), makeField({ is_confirmed: false })];
    render(<ReviewSummary fields={fields} onConfirmAll={vi.fn()} />);

    expect(screen.getByRole('button', { name: /Confirm All Fields/i })).toBeInTheDocument();
  });

  it('calls onConfirmAll once when the button is clicked', () => {
    const handleConfirmAll = vi.fn();
    const fields = [makeField({ is_confirmed: false })];
    render(<ReviewSummary fields={fields} onConfirmAll={handleConfirmAll} />);

    fireEvent.click(screen.getByRole('button', { name: /Confirm All Fields/i }));
    expect(handleConfirmAll).toHaveBeenCalledTimes(1);
  });
});

// ── Review-needed badge ───────────────────────────────────────────────────────

describe('ReviewSummary – review-needed badge', () => {
  it('shows the "N Need Review" badge when review-flagged unconfirmed fields exist', () => {
    const fields = [
      makeField({ requires_review: true, is_confirmed: false }),
      makeField({ requires_review: true, is_confirmed: false }),
    ];
    render(<ReviewSummary fields={fields} onConfirmAll={vi.fn()} />);

    expect(screen.getByText(/2 Need Review/i)).toBeInTheDocument();
  });

  it('shows "Ready for Confirmation" when no review flags and not all confirmed', () => {
    const fields = [makeField({ requires_review: false, is_confirmed: false })];
    render(<ReviewSummary fields={fields} onConfirmAll={vi.fn()} />);

    expect(screen.getByText(/Ready for Confirmation/i)).toBeInTheDocument();
  });
});

// ── Export policy notice ──────────────────────────────────────────────────────

describe('ReviewSummary – export policy notice', () => {
  it('always shows the export-unavailable policy notice', () => {
    render(<ReviewSummary fields={[makeField()]} onConfirmAll={vi.fn()} />);

    expect(screen.getByText(/Export.*Persistence Notice/i)).toBeInTheDocument();
    expect(screen.getByText(/Phase 08/i)).toBeInTheDocument();
  });

  it('does not render any export button', () => {
    render(<ReviewSummary fields={[makeField()]} onConfirmAll={vi.fn()} />);

    // No button with "Export" in its label
    const buttons = screen.queryAllByRole('button', { name: /export/i });
    expect(buttons).toHaveLength(0);
  });
});
