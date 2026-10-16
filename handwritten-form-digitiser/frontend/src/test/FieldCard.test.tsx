import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { FieldCard } from '../components/FieldCard';
import type { DigitizedField } from '../types/api';

// ── Fixtures ─────────────────────────────────────────────────────────────────

function makeField(overrides: Partial<DigitizedField> = {}): DigitizedField {
  return {
    field_id: 'field_name',
    field_name: 'name',
    field_type: 'name',
    raw_ocr_text: 'रमेश कुमार',
    current_value: 'रमेश कुमार',
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

// ── OCR prediction display ────────────────────────────────────────────────────

describe('FieldCard – machine OCR prediction', () => {
  it('displays the raw OCR text in the read-only prediction box', () => {
    render(
      <FieldCard
        field={makeField({ raw_ocr_text: 'रमेश कुमार' })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.getByText('रमेश कुमार')).toBeInTheDocument();
    expect(screen.getByText(/Machine OCR Prediction/i)).toBeInTheDocument();
  });

  it('shows confidence percentage when a numeric confidence is provided', () => {
    render(
      <FieldCard
        field={makeField({ confidence: 0.87, is_confidence_calibrated: true })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.getByText(/87\.0%/)).toBeInTheDocument();
    // Must NOT show "(heuristic)" for calibrated confidence
    expect(screen.queryByText(/heuristic/i)).not.toBeInTheDocument();
  });

  it('appends (heuristic) when confidence is not calibrated', () => {
    render(
      <FieldCard
        field={makeField({ confidence: 0.62, is_confidence_calibrated: false })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.getByText(/heuristic/i)).toBeInTheDocument();
  });

  it('shows "Confidence: N/A" when confidence is null', () => {
    render(
      <FieldCard
        field={makeField({ confidence: null })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.getByText(/Confidence: N\/A/i)).toBeInTheDocument();
  });

  it('shows "[Empty OCR output]" placeholder when raw_ocr_text is empty', () => {
    render(
      <FieldCard
        field={makeField({ raw_ocr_text: '', current_value: '' })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.getByText(/Empty OCR output/i)).toBeInTheDocument();
  });
});

// ── Editable input ────────────────────────────────────────────────────────────

describe('FieldCard – editable input', () => {
  it('calls onUpdateValue with new text when user types', () => {
    const handleUpdate = vi.fn();
    render(
      <FieldCard
        field={makeField()}
        onUpdateValue={handleUpdate}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    const input = screen.getByPlaceholderText(/Enter or correct name/i);
    fireEvent.change(input, { target: { value: 'रमेश शर्मा' } });

    expect(handleUpdate).toHaveBeenCalledWith('field_name', 'रमेश शर्मा');
  });

  it('shows the Edited badge when is_manually_edited is true', () => {
    render(
      <FieldCard
        field={makeField({ is_manually_edited: true, current_value: 'रमेश शर्मा' })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.getByText('Edited')).toBeInTheDocument();
  });

  it('does NOT show the Edited badge when field is unmodified', () => {
    render(
      <FieldCard
        field={makeField({ is_manually_edited: false })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.queryByText('Edited')).not.toBeInTheDocument();
  });
});

// ── Confirm / Revert buttons ──────────────────────────────────────────────────

describe('FieldCard – confirm and revert controls', () => {
  it('calls onConfirmField with the field ID when Confirm Value is clicked', () => {
    const handleConfirm = vi.fn();
    render(
      <FieldCard
        field={makeField()}
        onUpdateValue={vi.fn()}
        onConfirmField={handleConfirm}
        onRevertField={vi.fn()}
      />
    );

    fireEvent.click(screen.getByText(/Confirm Value/i));
    expect(handleConfirm).toHaveBeenCalledWith('field_name');
  });

  it('shows "Approved ✓" on the button when the field is already confirmed', () => {
    render(
      <FieldCard
        field={makeField({ is_confirmed: true })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.getByText(/Approved/i)).toBeInTheDocument();
    expect(screen.queryByText(/Confirm Value/i)).not.toBeInTheDocument();
  });

  it('shows the Revert button only when the field is manually edited', () => {
    render(
      <FieldCard
        field={makeField({ is_manually_edited: true })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.getByText(/Revert to OCR/i)).toBeInTheDocument();
  });

  it('calls onRevertField with the field ID when Revert button is clicked', () => {
    const handleRevert = vi.fn();
    render(
      <FieldCard
        field={makeField({ is_manually_edited: true })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={handleRevert}
      />
    );

    fireEvent.click(screen.getByText(/Revert to OCR/i));
    expect(handleRevert).toHaveBeenCalledWith('field_name');
  });

  it('shows "Unchanged from OCR" when field has not been manually edited', () => {
    render(
      <FieldCard
        field={makeField({ is_manually_edited: false })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.getByText(/Unchanged from OCR/i)).toBeInTheDocument();
  });
});

// ── Review status indicators ──────────────────────────────────────────────────

describe('FieldCard – review status indicators', () => {
  it('shows "Needs Review" badge when requires_review is true', () => {
    render(
      <FieldCard
        field={makeField({ requires_review: true, review_reasons: ['Low OCR confidence'] })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.getByText(/Needs Review/i)).toBeInTheDocument();
  });

  it('renders review_reasons inside the warnings panel', () => {
    render(
      <FieldCard
        field={makeField({
          requires_review: true,
          review_reasons: ['Low OCR confidence'],
          warning_codes: ['CONF_LOW'],
        })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.getByText('Low OCR confidence')).toBeInTheDocument();
    expect(screen.getByText(/Code: CONF_LOW/i)).toBeInTheDocument();
  });

  it('shows "Invalid" badge when validation_status is INVALID', () => {
    render(
      <FieldCard
        field={makeField({ validation_status: 'INVALID', review_reasons: ['Cannot parse date'] })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.getByText(/Invalid/i)).toBeInTheDocument();
  });

  it('shows "Confirmed" badge when field is confirmed', () => {
    render(
      <FieldCard
        field={makeField({ is_confirmed: true })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.getByText('Confirmed')).toBeInTheDocument();
  });

  it('shows "Valid" badge for a clean field with no review flags', () => {
    render(
      <FieldCard
        field={makeField({ validation_status: 'VALID', requires_review: false })}
        onUpdateValue={vi.fn()}
        onConfirmField={vi.fn()}
        onRevertField={vi.fn()}
      />
    );

    expect(screen.getByText('Valid')).toBeInTheDocument();
  });
});
