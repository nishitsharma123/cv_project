import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EngineSelector } from '../components/EngineSelector';
import type { EngineCapabilityData } from '../types/api';

// ── Fixtures ─────────────────────────────────────────────────────────────────

const tesseractEngine: EngineCapabilityData = {
  engine_id: 'tesseract',
  display_name: 'Tesseract Hindi (hin)',
  supported_scripts: ['Devanagari'],
  is_available: true,
  unavailability_reason: null,
  setup_instructions: null,
};

const trocr_unavailable: EngineCapabilityData = {
  engine_id: 'trocr_devanagari',
  display_name: 'TrOCR Devanagari',
  supported_scripts: ['Devanagari'],
  is_available: false,
  unavailability_reason: 'transformers package not installed',
  setup_instructions: 'pip install transformers',
};

// ── Rendering ─────────────────────────────────────────────────────────────────

describe('EngineSelector component', () => {
  it('renders the label and select element', () => {
    render(
      <EngineSelector
        engines={[tesseractEngine]}
        selectedEngineId="tesseract"
        onSelectEngine={vi.fn()}
      />
    );

    expect(screen.getByLabelText(/OCR Recognition Engine/i)).toBeInTheDocument();
  });

  it('lists all provided engines as options', () => {
    render(
      <EngineSelector
        engines={[tesseractEngine, trocr_unavailable]}
        selectedEngineId="tesseract"
        onSelectEngine={vi.fn()}
      />
    );

    // Both option labels must be present
    expect(screen.getByText(/Tesseract Hindi/i)).toBeInTheDocument();
    expect(screen.getByText(/TrOCR Devanagari/i)).toBeInTheDocument();
  });

  it('marks unavailable engines with "(Not Installed)" in the option text', () => {
    render(
      <EngineSelector
        engines={[trocr_unavailable]}
        selectedEngineId="trocr_devanagari"
        onSelectEngine={vi.fn()}
      />
    );

    const option = screen.getByRole('option', { name: /Not Installed/i });
    expect(option).toBeInTheDocument();
  });

  // ── Availability status hint ──────────────────────────────────────────────

  it('shows "Engine ready" hint with supported scripts for an available engine', () => {
    render(
      <EngineSelector
        engines={[tesseractEngine]}
        selectedEngineId="tesseract"
        onSelectEngine={vi.fn()}
      />
    );

    expect(screen.getByText(/Engine ready/i)).toBeInTheDocument();
    expect(screen.getByText(/Devanagari/i)).toBeInTheDocument();
  });

  it('shows the unavailability reason for an unavailable engine', () => {
    render(
      <EngineSelector
        engines={[trocr_unavailable]}
        selectedEngineId="trocr_devanagari"
        onSelectEngine={vi.fn()}
      />
    );

    expect(screen.getByText(/transformers package not installed/i)).toBeInTheDocument();
  });

  it('shows fallback message when unavailability_reason is null for an unavailable engine', () => {
    const noReasonEngine: EngineCapabilityData = {
      ...trocr_unavailable,
      unavailability_reason: null,
    };

    render(
      <EngineSelector
        engines={[noReasonEngine]}
        selectedEngineId="trocr_devanagari"
        onSelectEngine={vi.fn()}
      />
    );

    expect(screen.getByText(/Engine runtime not found/i)).toBeInTheDocument();
  });

  // ── Interaction ───────────────────────────────────────────────────────────

  it('calls onSelectEngine with the new engine ID when selection changes', () => {
    const handleSelect = vi.fn();
    render(
      <EngineSelector
        engines={[tesseractEngine, trocr_unavailable]}
        selectedEngineId="tesseract"
        onSelectEngine={handleSelect}
      />
    );

    const select = screen.getByLabelText(/OCR Recognition Engine/i);
    fireEvent.change(select, { target: { value: 'trocr_devanagari' } });

    expect(handleSelect).toHaveBeenCalledWith('trocr_devanagari');
  });

  // ── Disabled states ───────────────────────────────────────────────────────

  it('disables the select element when disabled prop is true', () => {
    render(
      <EngineSelector
        engines={[tesseractEngine]}
        selectedEngineId="tesseract"
        onSelectEngine={vi.fn()}
        disabled
      />
    );

    expect(screen.getByLabelText(/OCR Recognition Engine/i)).toBeDisabled();
  });

  it('disables the select element when engines array is empty', () => {
    render(
      <EngineSelector
        engines={[]}
        selectedEngineId=""
        onSelectEngine={vi.fn()}
      />
    );

    expect(screen.getByRole('combobox')).toBeDisabled();
  });
});
