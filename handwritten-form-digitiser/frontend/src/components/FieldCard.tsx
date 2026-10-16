import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  RotateCcw,
  Sparkles,
  ShieldAlert,
  UserCheck,
} from 'lucide-react';
import { DigitizedField } from '../types/api';

interface FieldCardProps {
  field: DigitizedField;
  onUpdateValue: (fieldId: string, newValue: string) => void;
  onConfirmField: (fieldId: string) => void;
  onRevertField: (fieldId: string) => void;
}

export const FieldCard: React.FC<FieldCardProps> = ({
  field,
  onUpdateValue,
  onConfirmField,
  onRevertField,
}) => {
  const [showCropModal, setShowCropModal] = useState(false);

  const isInvalid = field.validation_status === 'INVALID';
  const isWarning = field.validation_status === 'WARNING';
  const isValid = field.validation_status === 'VALID';

  const borderColor = field.is_confirmed
    ? 'border-emerald-300 bg-emerald-50/20 ring-1 ring-emerald-300'
    : isInvalid
    ? 'border-rose-300 bg-rose-50/20 ring-1 ring-rose-200'
    : field.requires_review
    ? 'border-amber-300 bg-amber-50/20 ring-1 ring-amber-200'
    : 'border-slate-200 bg-white';

  return (
    <div className={`border rounded-xl p-4 transition-all duration-200 shadow-sm ${borderColor}`}>
      {/* Top Header Row */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <div className="flex items-center space-x-2">
            <h4 className="text-sm font-semibold text-slate-900 capitalize">
              {field.field_name.replace(/_/g, ' ')}
            </h4>
            <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
              {field.field_type}
            </span>
          </div>
          <span className="text-[11px] text-slate-400 font-mono">ID: {field.field_id}</span>
        </div>

        {/* Status & Review Badges */}
        <div className="flex flex-wrap items-center gap-1.5 justify-end">
          {field.is_confirmed ? (
            <span className="inline-flex items-center text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
              <UserCheck className="w-3 h-3 mr-1 text-emerald-600" />
              Confirmed
            </span>
          ) : isInvalid ? (
            <span className="inline-flex items-center text-[11px] font-medium px-2 py-0.5 rounded-full bg-rose-100 text-rose-800 border border-rose-300">
              <XCircle className="w-3 h-3 mr-1 text-rose-600" />
              Invalid
            </span>
          ) : isWarning || field.requires_review ? (
            <span className="inline-flex items-center text-[11px] font-medium px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300">
              <AlertTriangle className="w-3 h-3 mr-1 text-amber-600" />
              Needs Review
            </span>
          ) : (
            <span className="inline-flex items-center text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200">
              <CheckCircle2 className="w-3 h-3 mr-1 text-emerald-600" />
              Valid
            </span>
          )}

          {field.is_manually_edited && (
            <span className="inline-flex items-center text-[10px] font-semibold px-2 py-0.5 rounded bg-blue-100 text-blue-800 border border-blue-200">
              Edited
            </span>
          )}
        </div>
      </div>

      {/* Crop Preview (if available from segmentation) */}
      {field.crop_preview_url && (
        <div className="mb-3">
          <span className="text-[11px] font-medium text-slate-500 block mb-1">
            Segmented Field Crop (ROI):
          </span>
          <div
            onClick={() => setShowCropModal(true)}
            className="cursor-pointer bg-slate-900 border border-slate-200 rounded-lg p-1.5 inline-block max-w-full hover:ring-2 hover:ring-blue-500 transition-shadow"
            title="Click to expand crop preview"
          >
            <img
              src={field.crop_preview_url}
              alt={`${field.field_name} crop preview`}
              className="max-h-16 w-auto object-contain rounded"
            />
          </div>
        </div>
      )}

      {/* Machine OCR Reference Box (Never Mutated) */}
      <div className="mb-3 p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-xs">
        <div className="flex items-center justify-between text-slate-500 mb-1">
          <span className="flex items-center font-medium">
            <Sparkles className="w-3 h-3 mr-1 text-blue-600" />
            Machine OCR Prediction
          </span>
          {field.confidence !== null && field.confidence !== undefined ? (
            <span
              className={`font-mono text-[11px] ${
                field.confidence >= 0.75 ? 'text-emerald-700' : 'text-amber-700 font-semibold'
              }`}
            >
              Confidence: {(field.confidence * 100).toFixed(1)}%
              {!field.is_confidence_calibrated && ' (heuristic)'}
            </span>
          ) : (
            <span className="text-slate-400 text-[11px]">Confidence: N/A</span>
          )}
        </div>
        <p className="font-devanagari text-slate-800 font-medium text-sm break-words">
          {field.raw_ocr_text || <span className="text-slate-400 italic">[Empty OCR output]</span>}
        </p>
      </div>

      {/* Editable Input for Human-in-the-Loop Correction */}
      <div className="space-y-1.5 mb-3">
        <label
          htmlFor={`input-${field.field_id}`}
          className="text-xs font-semibold text-slate-700 flex items-center justify-between"
        >
          <span>Digitized / Corrected Value:</span>
          {field.normalized_text && field.normalized_text !== field.current_value && (
            <span className="text-[11px] text-blue-600 font-normal">
              Normalized: {field.normalized_text}
            </span>
          )}
        </label>
        <div className="relative">
          <input
            id={`input-${field.field_id}`}
            type="text"
            value={field.current_value}
            onChange={(e) => onUpdateValue(field.field_id, e.target.value)}
            className={`w-full font-devanagari text-sm px-3.5 py-2.5 rounded-lg border focus:outline-none focus:ring-2 transition-shadow ${
              field.is_manually_edited
                ? 'border-blue-500 bg-blue-50/20 text-blue-950 font-semibold focus:ring-blue-500'
                : 'border-slate-300 bg-white text-slate-900 focus:ring-blue-600'
            }`}
            placeholder={`Enter or correct ${field.field_name}...`}
          />
        </div>
      </div>

      {/* Warnings & Review Reasons */}
      {(field.warning_codes.length > 0 || field.review_reasons.length > 0) && (
        <div className="mb-3 p-2.5 rounded-lg bg-amber-50/80 border border-amber-200 text-xs text-amber-900">
          <div className="flex items-center space-x-1 font-semibold text-amber-950 mb-1">
            <ShieldAlert className="w-3.5 h-3.5 text-amber-700" />
            <span>Validation Flags:</span>
          </div>
          <ul className="list-disc pl-4 space-y-0.5 text-amber-800 text-[11px]">
            {field.review_reasons.map((r, i) => (
              <li key={`reason-${i}`}>{r}</li>
            ))}
            {field.warning_codes.map((c, i) => (
              <li key={`code-${i}`} className="font-mono text-[10px] text-amber-700">
                Code: {c}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Action Buttons: Confirm / Revert */}
      <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
        {field.is_manually_edited ? (
          <button
            onClick={() => onRevertField(field.field_id)}
            className="inline-flex items-center space-x-1 text-slate-500 hover:text-slate-800 transition-colors font-medium"
            title="Discard edits and restore original machine OCR text"
          >
            <RotateCcw className="w-3 h-3" />
            <span>Revert to OCR</span>
          </button>
        ) : (
          <span className="text-[11px] text-slate-400">Unchanged from OCR</span>
        )}

        <button
          onClick={() => onConfirmField(field.field_id)}
          className={`inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
            field.is_confirmed
              ? 'bg-emerald-600 text-white shadow-sm hover:bg-emerald-700'
              : 'bg-slate-900 text-white hover:bg-slate-800 shadow-sm'
          }`}
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          <span>{field.is_confirmed ? 'Approved ✓' : 'Confirm Value'}</span>
        </button>
      </div>

      {/* Crop Expansion Modal */}
      {showCropModal && field.crop_preview_url && (
        <div
          className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
          onClick={() => setShowCropModal(false)}
        >
          <div className="bg-white rounded-xl p-4 max-w-lg w-full" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-2">
              <h5 className="text-sm font-semibold text-slate-800">
                Crop ROI: {field.field_name}
              </h5>
              <button
                onClick={() => setShowCropModal(false)}
                className="text-xs text-slate-500 hover:text-slate-800"
              >
                Close ✕
              </button>
            </div>
            <div className="bg-slate-900 p-2 rounded-lg flex items-center justify-center">
              <img
                src={field.crop_preview_url}
                alt="Enlarged crop preview"
                className="max-h-72 w-auto object-contain"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
