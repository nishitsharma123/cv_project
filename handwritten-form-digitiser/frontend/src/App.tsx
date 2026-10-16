import React, { useEffect, useState } from 'react';
import { Play, RotateCcw, AlertTriangle, FileSpreadsheet } from 'lucide-react';
import { Header } from './components/Header';
import { FileUpload } from './components/FileUpload';
import { TemplateSelector } from './components/TemplateSelector';
import { EngineSelector } from './components/EngineSelector';
import { ProcessingStatus, PipelineStep } from './components/ProcessingStatus';
import { DocumentPreview } from './components/DocumentPreview';
import { FieldCard } from './components/FieldCard';
import { ReviewSummary } from './components/ReviewSummary';
import { apiService, ApiError } from './services/api';
import { DigitizedField, EngineCapabilityData, FormTemplateSummary } from './types/api';

export const App: React.FC = () => {
  // Backend & Metadata State
  const [backendHealth, setBackendHealth] = useState<{ online: boolean; version?: string } | null>(null);
  const [templates, setTemplates] = useState<FormTemplateSummary[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>('devanagari_synthetic_v1');
  const [engines, setEngines] = useState<EngineCapabilityData[]>([]);
  const [selectedEngineId, setSelectedEngineId] = useState<string>('mock');

  // Form Input State
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  // Pipeline Execution State
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [processingStep, setProcessingStep] = useState<PipelineStep | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);

  // Results State
  const [annotatedPreviewUrl, setAnnotatedPreviewUrl] = useState<string | null>(null);
  const [digitizedFields, setDigitizedFields] = useState<DigitizedField[]>([]);
  const [inferenceTimeMs, setInferenceTimeMs] = useState<number>(0);

  // Load initial backend dependencies
  const checkHealthAndLoadMetadata = async () => {
    try {
      const health = await apiService.checkHealth();
      setBackendHealth({ online: true, version: health.version });
    } catch {
      setBackendHealth({ online: false });
    }

    try {
      const tpls = await apiService.fetchTemplates();
      setTemplates(tpls);
      if (tpls.length > 0 && !tpls.some((t) => t.template_id === selectedTemplateId)) {
        setSelectedTemplateId(tpls[0].template_id);
      }
    } catch {
      // Handled via state
    }

    try {
      const engs = await apiService.fetchEngines();
      setEngines(engs);
      // Prefer mock for testing if others not available, or pick first available
      const avail = engs.find((e) => e.is_available);
      if (avail) {
        setSelectedEngineId(avail.engine_id);
      } else if (engs.length > 0) {
        setSelectedEngineId(engs[0].engine_id);
      }
    } catch {
      // Handled via state
    }
  };

  useEffect(() => {
    checkHealthAndLoadMetadata();
  }, []);

  // Update object URL when file changes
  useEffect(() => {
    if (!selectedFile) {
      setObjectUrl(null);
      return;
    }
    const url = URL.createObjectURL(selectedFile);
    setObjectUrl(url);

    return () => {
      URL.revokeObjectURL(url);
    };
  }, [selectedFile]);

  const handleProcessForm = async () => {
    if (!selectedFile) {
      setErrorMessage('Please select or drop a form image before starting processing.');
      setErrorCode('NO_FILE_SELECTED');
      return;
    }

    setIsProcessing(true);
    setErrorMessage(null);
    setErrorCode(null);
    setWarnings([]);

    try {
      const result = await apiService.executeDigitizationPipeline(
        selectedFile,
        selectedTemplateId,
        selectedEngineId,
        (step) => setProcessingStep(step)
      );

      setAnnotatedPreviewUrl(result.annotatedPreviewUrl || null);
      setDigitizedFields(result.fields);
      setInferenceTimeMs(result.totalInferenceTimeMs);
      setWarnings(result.warnings);
    } catch (err: any) {
      if (err instanceof ApiError) {
        setErrorMessage(err.message);
        setErrorCode(err.code);
      } else {
        setErrorMessage(err?.message || 'Unexpected failure during form processing.');
        setErrorCode('UNEXPECTED_ERROR');
      }
    } finally {
      setIsProcessing(false);
      setProcessingStep(null);
    }
  };

  const handleUpdateFieldValue = async (fieldId: string, newValue: string) => {
    setDigitizedFields((prev) =>
      prev.map((f) => {
        if (f.field_id !== fieldId) return f;
        const isEdited = newValue !== f.raw_ocr_text;
        return {
          ...f,
          current_value: newValue,
          is_manually_edited: isEdited,
          is_confirmed: false, // Reset confirmation when user edits
        };
      })
    );

    // Interactive re-validation against backend domain rules
    try {
      const target = digitizedFields.find((f) => f.field_id === fieldId);
      if (!target) return;

      const reval = await apiService.validateField(
        fieldId,
        target.field_type,
        newValue,
        target.confidence,
        target.is_confidence_calibrated
      );

      setDigitizedFields((prev) =>
        prev.map((f) => {
          if (f.field_id !== fieldId) return f;
          return {
            ...f,
            validation_status: reval.validation_status,
            requires_review: reval.requires_review,
            review_reasons: reval.review_reasons,
            warning_codes: reval.warning_codes,
            normalized_text: reval.normalized_text,
          };
        })
      );
    } catch {
      // Ignore background revalidation failure; local edit is preserved
    }
  };

  const handleConfirmField = (fieldId: string) => {
    setDigitizedFields((prev) =>
      prev.map((f) => (f.field_id === fieldId ? { ...f, is_confirmed: !f.is_confirmed } : f))
    );
  };

  const handleRevertField = (fieldId: string) => {
    setDigitizedFields((prev) =>
      prev.map((f) => {
        if (f.field_id !== fieldId) return f;
        return {
          ...f,
          current_value: f.normalized_text !== null ? f.normalized_text : f.raw_ocr_text,
          is_manually_edited: false,
          is_confirmed: false,
        };
      })
    );
  };

  const handleConfirmAll = () => {
    setDigitizedFields((prev) => prev.map((f) => ({ ...f, is_confirmed: true })));
  };

  const handleReset = () => {
    setSelectedFile(null);
    setAnnotatedPreviewUrl(null);
    setDigitizedFields([]);
    setErrorMessage(null);
    setErrorCode(null);
    setWarnings([]);
    setInferenceTimeMs(0);
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col font-sans">
      <Header backendHealth={backendHealth} onRefreshHealth={checkHealthAndLoadMetadata} />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Intro Banner */}
        <div className="mb-6 bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h2 className="text-lg font-bold text-slate-900">
                Devanagari Form Ingestion & Verification
              </h2>
              <p className="text-xs text-slate-600 mt-1 max-w-2xl leading-relaxed">
                Upload scanned or photographed Devanagari application forms. The system validates image integrity, detects layout bounding boxes via OpenCV, executes Indic OCR, and evaluates calendar and numeric domain rules.
              </p>
            </div>
            {digitizedFields.length > 0 && (
              <button
                onClick={handleReset}
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg border border-slate-300 text-xs font-semibold text-slate-700 hover:bg-slate-100 transition-colors shadow-sm self-start sm:self-auto"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Reset Form</span>
              </button>
            )}
          </div>
        </div>

        {/* Two-Column Responsive Workspace */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left Column: Input, Controls & Inspection Canvas (5 Cols on LG) */}
          <div className="lg:col-span-5 space-y-5">
            <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm space-y-4">
              <FileUpload
                selectedFile={selectedFile}
                onFileSelected={(f) => {
                  setSelectedFile(f);
                  setAnnotatedPreviewUrl(null);
                  setDigitizedFields([]);
                  setErrorMessage(null);
                }}
                disabled={isProcessing}
              />

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                <TemplateSelector
                  templates={templates}
                  selectedTemplateId={selectedTemplateId}
                  onSelectTemplate={setSelectedTemplateId}
                  disabled={isProcessing}
                />
                <EngineSelector
                  engines={engines}
                  selectedEngineId={selectedEngineId}
                  onSelectEngine={setSelectedEngineId}
                  disabled={isProcessing}
                />
              </div>

              <button
                onClick={handleProcessForm}
                disabled={!selectedFile || isProcessing}
                className={`w-full py-3 px-4 rounded-xl text-sm font-semibold text-white flex items-center justify-center space-x-2 transition-all shadow-sm ${
                  !selectedFile || isProcessing
                    ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                    : 'bg-blue-700 hover:bg-blue-800 active:bg-blue-900 shadow-blue-700/20'
                }`}
              >
                <Play className="w-4 h-4 fill-current" />
                <span>{isProcessing ? 'Processing Document...' : 'Digitize & Segment Form'}</span>
              </button>
            </div>

            {/* Document Canvas Preview */}
            <DocumentPreview
              originalFileUrl={objectUrl}
              annotatedPreviewUrl={annotatedPreviewUrl}
              fileName={selectedFile?.name}
            />
          </div>

          {/* Right Column: Processing States, Results & Review Workflow (7 Cols on LG) */}
          <div className="lg:col-span-7 space-y-5">
            {/* Status Notifications */}
            <ProcessingStatus
              isProcessing={isProcessing}
              currentStep={processingStep}
              errorMessage={errorMessage}
              errorCode={errorCode}
              onDismissError={() => setErrorMessage(null)}
              warnings={warnings}
            />

            {/* Extracted Fields Workspace */}
            {digitizedFields.length > 0 ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <FileSpreadsheet className="w-5 h-5 text-blue-700" />
                    <h3 className="text-base font-bold text-slate-900">
                      Extracted Form Fields ({digitizedFields.length})
                    </h3>
                  </div>
                  {inferenceTimeMs > 0 && (
                    <span className="text-xs font-mono text-slate-500 bg-slate-100 px-2 py-0.5 rounded border border-slate-200">
                      OCR: {inferenceTimeMs.toFixed(1)}ms
                    </span>
                  )}
                </div>

                {/* Per-field cards */}
                <div className="space-y-3">
                  {digitizedFields.map((field) => (
                    <FieldCard
                      key={field.field_id}
                      field={field}
                      onUpdateValue={handleUpdateFieldValue}
                      onConfirmField={handleConfirmField}
                      onRevertField={handleRevertField}
                    />
                  ))}
                </div>

                {/* Review & Confirmation Summary */}
                <ReviewSummary
                  fields={digitizedFields}
                  onConfirmAll={handleConfirmAll}
                />
              </div>
            ) : (
              !isProcessing && !errorMessage && (
                <div className="bg-white border border-dashed border-slate-300 rounded-xl p-10 text-center text-slate-500 shadow-sm">
                  <div className="w-12 h-12 mx-auto mb-3 rounded-full bg-slate-100 flex items-center justify-center text-slate-400">
                    <FileSpreadsheet className="w-6 h-6 stroke-1" />
                  </div>
                  <h4 className="text-sm font-semibold text-slate-800 mb-1">
                    Ready to Extract
                  </h4>
                  <p className="text-xs text-slate-500 max-w-sm mx-auto">
                    Select a handwritten form image on the left and click <strong>"Digitize & Segment Form"</strong> to initiate the pipeline.
                  </p>
                </div>
              )
            )}
          </div>
        </div>
      </main>

      <footer className="bg-white border-t border-slate-200 py-4 mt-auto text-xs text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>Handwritten Indic-Script Form Digitiser • Phase 07 Frontend</span>
          <span>FastAPI + OpenCV + PyTorch/Tesseract + React/Vite/Tailwind</span>
        </div>
      </footer>
    </div>
  );
};

export default App;
