/** Centralized API client for Handwritten Indic-Script Form Digitiser backend. */

import {
  BoundingBox,
  DocumentValidationResponseData,
  EngineCapabilityData,
  Envelope,
  FormTemplateSummary,
  RecognitionResponseData,
  SegmentationResponseData,
  DigitizedField,
  FieldValidationResult,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000';

export class ApiError extends Error {
  code: string;
  details?: Array<{ field?: string; message: string }>;

  constructor(message: string, code: string = 'API_ERROR', details?: Array<{ field?: string; message: string }>) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.details = details;
  }
}

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  try {
    const res = await fetch(url, options);
    const json = await res.json().catch(() => null);

    if (!res.ok || (json && json.success === false)) {
      const code = json?.error?.code || `HTTP_${res.status}`;
      const msg = json?.error?.message || `Request failed with status ${res.status}`;
      const details = json?.error?.details;
      throw new ApiError(msg, code, details);
    }

    if (json && typeof json === 'object' && 'data' in json) {
      return json.data as T;
    }
    return json as T;
  } catch (err: any) {
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(
      err.message || 'Network connection failed. Verify that the FastAPI backend is running.',
      'NETWORK_ERROR'
    );
  }
}

export const apiService = {
  getBaseUrl(): string {
    return API_BASE;
  },

  async checkHealth(): Promise<{ status: string; version: string }> {
    return request<{ status: string; version: string }>('/api/health');
  },

  async fetchTemplates(): Promise<FormTemplateSummary[]> {
    return request<FormTemplateSummary[]>('/api/templates');
  },

  async fetchEngines(): Promise<EngineCapabilityData[]> {
    return request<EngineCapabilityData[]>('/api/recognize/engines');
  },

  async segmentForm(
    file: File,
    templateId: string = 'devanagari_synthetic_v1',
    strategy: string = 'hybrid'
  ): Promise<SegmentationResponseData> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('template_id', templateId);
    formData.append('strategy', strategy);

    return request<SegmentationResponseData>('/api/segment', {
      method: 'POST',
      body: formData,
    });
  },

  async recognizeForm(
    file: File,
    templateId: string = 'devanagari_synthetic_v1',
    engineId: string = 'mock',
    strategy: string = 'hybrid'
  ): Promise<RecognitionResponseData> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('template_id', templateId);
    formData.append('engine_id', engineId);
    formData.append('strategy', strategy);

    return request<RecognitionResponseData>('/api/recognize', {
      method: 'POST',
      body: formData,
    });
  },

  async validateDocument(
    templateId: string,
    fields: Record<string, { field_id: string; field_type: string; raw_text: string; confidence?: number | null; is_confidence_calibrated?: boolean; bounding_box?: BoundingBox | null }>,
    engineId?: string
  ): Promise<DocumentValidationResponseData> {
    return request<DocumentValidationResponseData>('/api/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        template_id: templateId,
        engine_id: engineId,
        fields,
      }),
    });
  },

  async validateField(
    fieldId: string,
    fieldType: string,
    rawText: string,
    confidence?: number | null,
    isCalibrated: boolean = false
  ): Promise<FieldValidationResult> {
    return request<FieldValidationResult>('/api/validate/field', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        field_id: fieldId,
        field_type: fieldType,
        raw_text: rawText,
        confidence: confidence ?? null,
        is_confidence_calibrated: isCalibrated,
      }),
    });
  },

  /** Orchestrates the full digitization pipeline: Segment -> Recognize -> Validate */
  async executeDigitizationPipeline(
    file: File,
    templateId: string,
    engineId: string,
    onProgress?: (step: 'SEGMENTING' | 'RECOGNIZING' | 'VALIDATING') => void
  ): Promise<{
    annotatedPreviewUrl?: string;
    fields: DigitizedField[];
    documentRequiresReview: boolean;
    totalInferenceTimeMs: number;
    warnings: string[];
  }> {
    // 1. Segmentation
    onProgress?.('SEGMENTING');
    const segData = await this.segmentForm(file, templateId, 'hybrid');

    // 2. Recognition
    onProgress?.('RECOGNIZING');
    const recData = await this.recognizeForm(file, templateId, engineId, 'hybrid');

    // 3. Validation
    onProgress?.('VALIDATING');
    const validationInput: Record<string, any> = {};

    for (const [fid, recField] of Object.entries(recData.fields)) {
      const segField = segData.fields[fid];
      validationInput[fid] = {
        field_id: fid,
        field_type: recField.field_type,
        raw_text: recField.text || recField.raw_text || '',
        confidence: recField.confidence > 0 ? recField.confidence : null,
        is_confidence_calibrated: recField.is_confidence_calibrated,
        bounding_box: segField?.bounding_box || null,
      };
    }

    const valData = await this.validateDocument(templateId, validationInput, engineId);

    // 4. Construct unified frontend fields
    const digitizedFields: DigitizedField[] = [];

    for (const [fid, valResult] of Object.entries(valData.fields)) {
      const segField = segData.fields[fid];
      const recField = recData.fields[fid];
      const cropUrl = segField?.crop_preview?.preview_data_url || null;

      digitizedFields.push({
        field_id: fid,
        field_name: segField?.field_name || fid,
        field_type: valResult.field_type,
        raw_ocr_text: valResult.raw_text,
        current_value: valResult.normalized_text !== null ? valResult.normalized_text : valResult.raw_text,
        is_manually_edited: false,
        is_confirmed: false,
        normalized_text: valResult.normalized_text,
        validation_status: valResult.validation_status,
        requires_review: valResult.requires_review,
        review_reasons: valResult.review_reasons,
        warning_codes: valResult.warning_codes,
        confidence: valResult.confidence,
        is_confidence_calibrated: valResult.is_confidence_calibrated,
        bounding_box: segField?.bounding_box || null,
        crop_preview_url: cropUrl,
      });
    }

    const accumulatedWarnings = [
      ...segData.warnings,
      ...recData.warnings,
      ...valData.warnings,
    ];

    return {
      annotatedPreviewUrl: segData.annotated_preview?.data_url,
      fields: digitizedFields,
      documentRequiresReview: valData.document_requires_review,
      totalInferenceTimeMs: recData.total_inference_time_ms,
      warnings: Array.from(new Set(accumulatedWarnings)),
    };
  },
};
