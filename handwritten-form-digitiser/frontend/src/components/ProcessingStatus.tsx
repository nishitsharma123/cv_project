import React from 'react';
import { Loader2, AlertCircle, CheckCircle, Info } from 'lucide-react';

export type PipelineStep = 'SEGMENTING' | 'RECOGNIZING' | 'VALIDATING';

interface ProcessingStatusProps {
  isProcessing: boolean;
  currentStep?: PipelineStep | null;
  errorMessage?: string | null;
  errorCode?: string | null;
  onDismissError?: () => void;
  warnings?: string[];
}

export const ProcessingStatus: React.FC<ProcessingStatusProps> = ({
  isProcessing,
  currentStep,
  errorMessage,
  errorCode,
  onDismissError,
  warnings = [],
}) => {
  if (errorMessage) {
    return (
      <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 text-rose-800 shadow-sm" role="alert">
        <div className="flex items-start justify-between">
          <div className="flex items-start space-x-3">
            <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-semibold text-rose-900">
                Processing Failed {errorCode ? `[${errorCode}]` : ''}
              </h3>
              <p className="text-xs text-rose-700 mt-1 leading-relaxed">
                {errorMessage}
              </p>
            </div>
          </div>
          {onDismissError && (
            <button
              onClick={onDismissError}
              className="text-xs text-rose-600 hover:text-rose-900 font-medium px-2 py-1 rounded hover:bg-rose-100 transition-colors"
            >
              Dismiss
            </button>
          )}
        </div>
      </div>
    );
  }

  if (isProcessing) {
    const steps: { key: PipelineStep; label: string; desc: string }[] = [
      { key: 'SEGMENTING', label: '1. Layout Segmentation', desc: 'Deskewing, contrast adjustment & bounding box detection' },
      { key: 'RECOGNIZING', label: '2. Devanagari OCR', desc: 'Running handwritten character recognition' },
      { key: 'VALIDATING', label: '3. Semantic Validation', desc: 'Checking calendar dates, digits & confidence levels' },
    ];

    return (
      <div className="bg-blue-50/70 border border-blue-200 rounded-xl p-5 shadow-sm text-slate-900" aria-live="polite">
        <div className="flex items-center space-x-3 mb-4">
          <Loader2 className="w-5 h-5 text-blue-700 animate-spin" />
          <h3 className="text-sm font-semibold text-blue-950">
            Digitizing Form Document...
          </h3>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {steps.map((st, idx) => {
            const isCurrent = currentStep === st.key;
            const isCompleted =
              (currentStep === 'RECOGNIZING' && idx === 0) ||
              (currentStep === 'VALIDATING' && idx <= 1);

            return (
              <div
                key={st.key}
                className={`p-3 rounded-lg border text-xs transition-colors ${
                  isCurrent
                    ? 'bg-white border-blue-600 shadow-sm ring-1 ring-blue-600'
                    : isCompleted
                    ? 'bg-emerald-50/60 border-emerald-200 text-emerald-900'
                    : 'bg-white/60 border-slate-200 text-slate-500 opacity-60'
                }`}
              >
                <div className="flex items-center space-x-1.5 font-semibold mb-1">
                  {isCompleted ? (
                    <CheckCircle className="w-4 h-4 text-emerald-600" />
                  ) : isCurrent ? (
                    <Loader2 className="w-3.5 h-3.5 text-blue-700 animate-spin" />
                  ) : (
                    <span className="w-3.5 h-3.5 rounded-full border border-slate-300 flex items-center justify-center text-[10px]">
                      {idx + 1}
                    </span>
                  )}
                  <span>{st.label}</span>
                </div>
                <p className="text-[11px] text-slate-500 leading-tight">{st.desc}</p>
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  if (warnings.length > 0) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-amber-900 shadow-sm">
        <div className="flex items-start space-x-3">
          <Info className="w-4 h-4 text-amber-700 flex-shrink-0 mt-0.5" />
          <div className="text-xs">
            <span className="font-semibold block mb-0.5">Pipeline Notices:</span>
            <ul className="list-disc pl-4 space-y-0.5 text-amber-800">
              {warnings.map((w, idx) => (
                <li key={idx}>{w}</li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    );
  }

  return null;
};
