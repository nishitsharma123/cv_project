import React, { useCallback, useEffect, useRef, useState } from 'react';
import { UploadCloud, Image as ImageIcon, X, AlertTriangle } from 'lucide-react';

interface FileUploadProps {
  onFileSelected: (file: File | null) => void;
  selectedFile: File | null;
  disabled?: boolean;
}

const MAX_SIZE_MB = 15;
const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/jpg'];

export const FileUpload: React.FC<FileUploadProps> = ({
  onFileSelected,
  selectedFile,
  disabled = false,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Manage memory by revoking temporary object URL on unmount or file change
  useEffect(() => {
    if (!selectedFile) {
      setPreviewUrl(null);
      return;
    }

    const objectUrl = URL.createObjectURL(selectedFile);
    setPreviewUrl(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [selectedFile]);

  const validateAndSelect = (file: File) => {
    setValidationError(null);

    // 1. File size check
    if (file.size === 0) {
      setValidationError('Uploaded file is empty (0 bytes). Please select a valid form image.');
      return;
    }

    const sizeMb = file.size / (1024 * 1024);
    if (sizeMb > MAX_SIZE_MB) {
      setValidationError(`File size (${sizeMb.toFixed(1)}MB) exceeds maximum limit of ${MAX_SIZE_MB}MB.`);
      return;
    }

    // 2. MIME type check
    if (!ACCEPTED_TYPES.includes(file.type.toLowerCase()) && !file.name.match(/\.(jpe?g|png)$/i)) {
      setValidationError('Unsupported format. Please upload a JPEG or PNG image.');
      return;
    }

    onFileSelected(file);
  };

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    if (!disabled) setIsDragging(true);
  }, [disabled]);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      if (disabled) return;

      const file = e.dataTransfer.files?.[0];
      if (file) {
        validateAndSelect(file);
      }
    },
    [disabled]
  );

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      validateAndSelect(file);
    }
    // Reset input value so re-selecting same file triggers change
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleClear = () => {
    setValidationError(null);
    onFileSelected(null);
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="w-full">
      <label className="block text-sm font-semibold text-slate-800 mb-1.5">
        Document Form Image
      </label>

      {!selectedFile ? (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !disabled && fileInputRef.current?.click()}
          className={`relative border-2 border-dashed rounded-xl p-6 sm:p-8 text-center cursor-pointer transition-all duration-200 ${
            isDragging
              ? 'border-blue-600 bg-blue-50/60'
              : 'border-slate-300 hover:border-slate-400 bg-white hover:bg-slate-50/50'
          } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
          role="button"
          tabIndex={disabled ? -1 : 0}
          onKeyDown={(e) => {
            if ((e.key === 'Enter' || e.key === ' ') && !disabled) {
              fileInputRef.current?.click();
            }
          }}
          aria-label="Upload document image"
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".png,.jpg,.jpeg,image/png,image/jpeg"
            onChange={handleFileInputChange}
            className="hidden"
            disabled={disabled}
          />
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 mb-3 rounded-full bg-blue-50 text-blue-700 flex items-center justify-center border border-blue-100">
              <UploadCloud className="w-6 h-6" />
            </div>
            <p className="text-sm font-medium text-slate-900 mb-1">
              Drag and drop your handwritten form here, or{' '}
              <span className="text-blue-700 underline font-semibold">browse files</span>
            </p>
            <p className="text-xs text-slate-500">
              Accepted formats: <span className="font-medium text-slate-700">PNG, JPEG, JPG</span> (Single page, max {MAX_SIZE_MB}MB)
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex items-center justify-between">
          <div className="flex items-center space-x-3 min-w-0">
            {previewUrl ? (
              <img
                src={previewUrl}
                alt="Upload thumbnail"
                className="w-12 h-12 object-cover rounded-lg border border-slate-200 flex-shrink-0"
              />
            ) : (
              <div className="w-12 h-12 rounded-lg bg-slate-100 flex items-center justify-center text-slate-500 flex-shrink-0">
                <ImageIcon className="w-6 h-6" />
              </div>
            )}
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-900 truncate" title={selectedFile.name}>
                {selectedFile.name}
              </p>
              <p className="text-xs text-slate-500">
                {formatFileSize(selectedFile.size)} • {selectedFile.type || 'image/jpeg'}
              </p>
            </div>
          </div>
          <button
            onClick={handleClear}
            disabled={disabled}
            className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
            title="Remove file"
            aria-label="Remove selected file"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      )}

      {validationError && (
        <div className="mt-2.5 p-3 rounded-lg bg-rose-50 border border-rose-200 flex items-start space-x-2 text-xs text-rose-700">
          <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
          <span>{validationError}</span>
        </div>
      )}
    </div>
  );
};
