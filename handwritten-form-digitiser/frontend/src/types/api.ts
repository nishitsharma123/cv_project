/** API response envelope interfaces and data contracts. */

export interface Envelope<T> {
  success: boolean;
  data: T;
  timestamp: string;
}

export interface ApiErrorPayload {
  code: string;
  message: string;
  details?: Array<{ field?: string; message: string }>;
}

export interface ApiErrorResponse {
  success: false;
  error: ApiErrorPayload;
  timestamp: string;
}

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
  width: number;
  height: number;
}

export interface PreviewData {
  format: string;
  data_url: string;
  width: number;
  height: number;
}

export interface FieldCropPreview {
  field_id: string;
  preview_data_url: string;
  width: number;
  height: number;
}

export interface FieldDetectionResult {
  field_id: string;
  field_name: string;
  field_type: string;
  bounding_box: BoundingBox;
  original_bounding_box?: BoundingBox | null;
  detection_method: string;
  status: string;
  confidence: number;
  warnings: string[];
  crop_preview?: FieldCropPreview;
}

export interface SegmentationResponseData {
  filename: string;
  template_id: string;
  strategy_applied: string;
  execution_time_ms: number;
  annotated_preview?: PreviewData;
  fields: Record<string, FieldDetectionResult>;
  warnings: string[];
}

export interface FormTemplateSummary {
  template_id: string;
  name: string;
  description: string;
  version: string;
  field_count: number;
  canonical_width: number;
  canonical_height: number;
}

export interface EngineCapabilityData {
  engine_id: string;
  display_name: string;
  supported_scripts: string[];
  is_available: boolean;
  unavailability_reason?: string | null;
  setup_instructions?: string | null;
}

export interface OCRResultData {
  field_id: string;
  field_type: string;
  model_id: string;
  status: string;
  text: string;
  raw_text: string;
  confidence: number;
  is_confidence_calibrated: boolean;
  inference_time_ms: number;
  warnings: string[];
}

export interface RecognitionResponseData {
  template_id: string;
  engine_id: string;
  total_inference_time_ms: number;
  fields: Record<string, OCRResultData>;
  warnings: string[];
}

export type ValidationStatus = 'VALID' | 'WARNING' | 'INVALID';

export interface FieldValidationResult {
  field_id: string;
  field_type: string;
  raw_text: string;
  normalized_text: string | null;
  validation_status: ValidationStatus;
  requires_review: boolean;
  review_reasons: string[];
  warning_codes: string[];
  confidence: number | null;
  is_confidence_calibrated: boolean;
  bounding_box?: BoundingBox | null;
  parsed_value?: any;
}

export interface DocumentValidationResponseData {
  template_id: string;
  engine_id?: string | null;
  total_fields: number;
  valid_fields: number;
  review_required_fields: number;
  document_requires_review: boolean;
  warnings: string[];
  fields: Record<string, FieldValidationResult>;
}

/** Unified frontend representation tracking machine OCR vs user corrections */
export interface DigitizedField {
  field_id: string;
  field_name: string;
  field_type: string;
  raw_ocr_text: string;           // Original unmodified OCR output
  current_value: string;          // User-edited value
  is_manually_edited: boolean;    // True if current_value differs from raw_ocr_text
  is_confirmed: boolean;          // True if user confirmed/approved the field
  normalized_text: string | null;
  validation_status: ValidationStatus;
  requires_review: boolean;
  review_reasons: string[];
  warning_codes: string[];
  confidence: number | null;
  is_confidence_calibrated: boolean;
  bounding_box?: BoundingBox | null;
  crop_preview_url?: string | null;
}
