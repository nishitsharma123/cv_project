import React from 'react';
import { FileText, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';

interface HeaderProps {
  backendHealth: { online: boolean; version?: string } | null;
  onRefreshHealth: () => void;
}

export const Header: React.FC<HeaderProps> = ({ backendHealth, onRefreshHealth }) => {
  return (
    <header className="bg-slate-900 border-b border-slate-800 text-white shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-600 rounded-lg shadow-inner">
            <FileText className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base sm:text-lg font-semibold tracking-tight leading-none text-white">
              Handwritten Indic-Script Form Digitiser
            </h1>
            <p className="text-xs text-slate-400 mt-1 hidden sm:block">
              Devanagari OCR, Field Segmentation & Human-in-the-Loop Review
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-4">
          {backendHealth ? (
            <div className="flex items-center space-x-2 text-xs">
              {backendHealth.online ? (
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-950 text-emerald-300 border border-emerald-800">
                  <CheckCircle2 className="w-3.5 h-3.5 mr-1 text-emerald-400" />
                  API v{backendHealth.version || '0.1.0'} Online
                </span>
              ) : (
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-rose-950 text-rose-300 border border-rose-800">
                  <AlertCircle className="w-3.5 h-3.5 mr-1 text-rose-400" />
                  Backend Disconnected
                </span>
              )}
              <button
                onClick={onRefreshHealth}
                title="Refresh backend status"
                className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800 transition-colors"
                aria-label="Refresh status"
              >
                <RefreshCw className="w-3.5 h-3.5" />
              </button>
            </div>
          ) : (
            <span className="text-xs text-slate-400 animate-pulse">Checking backend...</span>
          )}
        </div>
      </div>
    </header>
  );
};
