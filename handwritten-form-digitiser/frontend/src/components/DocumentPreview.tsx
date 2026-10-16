import React, { useState } from 'react';
import { Eye, Layers, Image as ImageIcon } from 'lucide-react';

interface DocumentPreviewProps {
  originalFileUrl?: string | null;
  annotatedPreviewUrl?: string | null;
  fileName?: string;
}

export const DocumentPreview: React.FC<DocumentPreviewProps> = ({
  originalFileUrl,
  annotatedPreviewUrl,
  fileName,
}) => {
  const [showAnnotated, setShowAnnotated] = useState<boolean>(Boolean(annotatedPreviewUrl));

  const activeUrl = showAnnotated && annotatedPreviewUrl ? annotatedPreviewUrl : originalFileUrl;

  if (!activeUrl) {
    return (
      <div className="bg-slate-100 border border-slate-200 rounded-xl h-96 flex flex-col items-center justify-center text-slate-400 p-6 text-center">
        <ImageIcon className="w-12 h-12 mb-2 stroke-1" />
        <p className="text-sm font-medium text-slate-500">No Document Preview Available</p>
        <p className="text-xs text-slate-400 mt-1">Upload a form image to inspect layout segmentation</p>
      </div>
    );
  }

  return (
    <div className="bg-white border border-slate-200 rounded-xl overflow-hidden shadow-sm flex flex-col">
      <div className="px-4 py-3 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Eye className="w-4 h-4 text-blue-700" />
          <span className="text-xs font-semibold text-slate-800 truncate max-w-[200px]" title={fileName}>
            {fileName || 'Form Document'}
          </span>
        </div>

        {annotatedPreviewUrl && (
          <div className="inline-flex rounded-lg p-0.5 bg-slate-200 border border-slate-300 text-xs">
            <button
              onClick={() => setShowAnnotated(true)}
              className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                showAnnotated
                  ? 'bg-white text-blue-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <span className="flex items-center space-x-1">
                <Layers className="w-3 h-3" />
                <span>Detected ROIs</span>
              </span>
            </button>
            <button
              onClick={() => setShowAnnotated(false)}
              className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                !showAnnotated
                  ? 'bg-white text-blue-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <span>Original</span>
            </button>
          </div>
        )}
      </div>

      <div className="relative bg-slate-950 flex items-center justify-center p-2 min-h-[360px] max-h-[540px] overflow-auto">
        <img
          src={activeUrl}
          alt="Document inspection canvas"
          className="max-h-[500px] w-auto object-contain rounded shadow"
        />
      </div>

      <div className="px-3 py-2 bg-slate-50 border-t border-slate-100 text-[11px] text-slate-500 flex items-center justify-between">
        <span>Mode: {showAnnotated ? 'Bounding Box Segmentation Overlay' : 'Raw Document View'}</span>
        <span>Inspection Canvas</span>
      </div>
    </div>
  );
};
