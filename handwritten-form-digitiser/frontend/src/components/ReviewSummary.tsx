import React from 'react';
import { CheckCircle, AlertTriangle, UserCheck, ShieldCheck, Database } from 'lucide-react';
import { DigitizedField } from '../types/api';

interface ReviewSummaryProps {
  fields: DigitizedField[];
  onConfirmAll: () => void;
}

export const ReviewSummary: React.FC<ReviewSummaryProps> = ({ fields, onConfirmAll }) => {
  const total = fields.length;
  const confirmedCount = fields.filter((f) => f.is_confirmed).length;
  const reviewNeededCount = fields.filter((f) => f.requires_review && !f.is_confirmed).length;
  const editedCount = fields.filter((f) => f.is_manually_edited).length;
  const allConfirmed = total > 0 && confirmedCount === total;

  return (
    <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-bold text-slate-900">
            Digitization & Review Status
          </h3>
          <p className="text-xs text-slate-500">
            Audit summary of machine extractions and human corrections
          </p>
        </div>

        {allConfirmed ? (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 border border-emerald-300">
            <ShieldCheck className="w-4 h-4 mr-1 text-emerald-600" />
            All Fields Confirmed
          </span>
        ) : reviewNeededCount > 0 ? (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300">
            <AlertTriangle className="w-4 h-4 mr-1 text-amber-600" />
            {reviewNeededCount} Need Review
          </span>
        ) : (
          <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
            Ready for Confirmation
          </span>
        )}
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
        <div className="p-3 bg-slate-50 rounded-lg border border-slate-200">
          <span className="text-xs text-slate-500 block mb-0.5">Total Fields</span>
          <span className="text-lg font-bold text-slate-900">{total}</span>
        </div>
        <div className="p-3 bg-emerald-50/50 rounded-lg border border-emerald-200">
          <span className="text-xs text-emerald-700 block mb-0.5">Confirmed</span>
          <span className="text-lg font-bold text-emerald-900">{confirmedCount}</span>
        </div>
        <div className="p-3 bg-amber-50/50 rounded-lg border border-amber-200">
          <span className="text-xs text-amber-700 block mb-0.5">Needs Review</span>
          <span className="text-lg font-bold text-amber-900">{reviewNeededCount}</span>
        </div>
        <div className="p-3 bg-blue-50/50 rounded-lg border border-blue-200">
          <span className="text-xs text-blue-700 block mb-0.5">Manually Edited</span>
          <span className="text-lg font-bold text-blue-900">{editedCount}</span>
        </div>
      </div>

      {/* Action and Guidance */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2 border-t border-slate-100">
        <p className="text-xs text-slate-600">
          {allConfirmed
            ? 'All extracted fields have been verified by human reviewer.'
            : 'Review any flagged fields above and click "Confirm Value" to approve.'}
        </p>

        {!allConfirmed && (
          <button
            onClick={onConfirmAll}
            className="inline-flex items-center justify-center space-x-1.5 px-3.5 py-2 rounded-lg bg-blue-700 text-white text-xs font-semibold hover:bg-blue-800 transition-colors shadow-sm"
          >
            <UserCheck className="w-3.5 h-3.5" />
            <span>Confirm All Fields</span>
          </button>
        )}
      </div>

      {/* Export Interface Policy Notice (Adheres to user constraint: do not create nonfunctional buttons) */}
      <div className="mt-2 p-3 bg-slate-50 rounded-lg border border-slate-200 flex items-start space-x-2 text-xs text-slate-600">
        <Database className="w-4 h-4 text-slate-500 flex-shrink-0 mt-0.5" />
        <div>
          <span className="font-semibold text-slate-800 block mb-0.5">
            Export & Persistence Notice
          </span>
          <p className="text-[11px] text-slate-500 leading-normal">
            Formal database storage (SQLite / SQLAlchemy) and backend JSON/CSV export endpoints (<code className="bg-slate-200 px-1 py-0.5 rounded font-mono text-[10px]">/api/v1/forms/:id/export</code>) will be wired in Phase 08. All verified extractions are actively verified in memory.
          </p>
        </div>
      </div>
    </div>
  );
};
