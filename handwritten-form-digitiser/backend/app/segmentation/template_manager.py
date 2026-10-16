"""Template manager for loading, validating, and caching form layout templates."""

import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.errors import NotFoundException, ValidationException

logger = logging.getLogger("app.segmentation.templates")

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


class FieldDefinition(BaseModel):
    """Specification of an individual form field region."""

    field_id: str = Field(..., description="Unique machine-readable field identifier")
    field_name: str = Field(..., description="Human-readable field name")
    field_type: str = Field(..., description="Field semantic type: NAME, DATE, or AMOUNT")
    normalized_box: List[float] = Field(
        ...,
        description="Normalized coordinates [norm_x1, norm_y1, norm_x2, norm_y2] in range [0.0, 1.0]",
    )
    required: bool = Field(default=True, description="Whether the field is mandatory")
    description: Optional[str] = Field(default=None, description="Detailed field instructions")
    padding_px: int = Field(default=4, description="Padding in pixels applied around the crop")
    expected_aspect_ratio_min: Optional[float] = Field(default=None, description="Expected minimum width/height")
    expected_aspect_ratio_max: Optional[float] = Field(default=None, description="Expected maximum width/height")

    @field_validator("normalized_box")
    @classmethod
    def validate_normalized_box(cls, v: List[float]) -> List[float]:
        if len(v) != 4:
            raise ValueError(f"normalized_box must contain exactly 4 floats [x1, y1, x2, y2], got {len(v)}")
        x1, y1, x2, y2 = v
        if not (0.0 <= x1 < x2 <= 1.0):
            raise ValueError(f"Invalid horizontal coordinates: 0.0 <= x1 ({x1}) < x2 ({x2}) <= 1.0 required")
        if not (0.0 <= y1 < y2 <= 1.0):
            raise ValueError(f"Invalid vertical coordinates: 0.0 <= y1 ({y1}) < y2 ({y2}) <= 1.0 required")
        return [float(c) for c in v]


class FormTemplate(BaseModel):
    """Declarative specification of a form layout and its constituent fields."""

    template_id: str = Field(..., description="Unique template identifier")
    name: str = Field(..., description="Display title of the template")
    version: str = Field(default="1.0.0", description="Template semver version")
    description: Optional[str] = Field(default=None, description="Detailed layout description")
    canonical_width: int = Field(default=800, description="Reference template width in pixels")
    canonical_height: int = Field(default=1000, description="Reference template height in pixels")
    aspect_ratio: float = Field(default=0.8, description="Reference aspect ratio (width / height)")
    fields: List[FieldDefinition] = Field(..., description="List of defined field regions")

    @model_validator(mode="after")
    def validate_field_ids_unique(self) -> "FormTemplate":
        field_ids = [f.field_id for f in self.fields]
        if len(field_ids) != len(set(field_ids)):
            duplicates = [fid for fid in field_ids if field_ids.count(fid) > 1]
            raise ValueError(f"Template '{self.template_id}' has duplicate field_ids: {set(duplicates)}")
        return self


class FormTemplateSummary(BaseModel):
    """Compact summary of a registered form template for listing endpoints."""

    template_id: str
    name: str
    version: str
    description: Optional[str] = None
    field_count: int
    fields: List[str]


class TemplateManager:
    """Manages discovery, loading, and retrieval of form layout templates."""

    _cache: Dict[str, FormTemplate] = {}

    @classmethod
    def get_template(cls, template_id: str) -> FormTemplate:
        """Retrieve a form template by ID, loading from disk if not cached."""
        if template_id in cls._cache:
            return cls._cache[template_id]

        file_path = TEMPLATES_DIR / f"{template_id}.json"
        if not file_path.exists():
            raise NotFoundException(
                message=f"Form template '{template_id}' was not found. Please register or specify a valid template.",
                code="TEMPLATE_NOT_FOUND",
                details=[{"field": "template_id", "message": f"Template '{template_id}' does not exist"}],
            )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            template = FormTemplate(**data)
            cls._cache[template_id] = template
            return template
        except json.JSONDecodeError as e:
            raise ValidationException(
                message=f"Template file '{template_id}.json' contains invalid JSON: {str(e)}",
                code="TEMPLATE_PARSE_ERROR",
            )
        except Exception as e:
            raise ValidationException(
                message=f"Failed to load template '{template_id}': {str(e)}",
                code="TEMPLATE_LOAD_ERROR",
            )

    @classmethod
    def list_templates(cls) -> List[FormTemplateSummary]:
        """List all discovered form templates."""
        summaries: List[FormTemplateSummary] = []
        if not TEMPLATES_DIR.exists():
            return summaries

        for file_path in TEMPLATES_DIR.glob("*.json"):
            template_id = file_path.stem
            try:
                template = cls.get_template(template_id)
                summaries.append(
                    FormTemplateSummary(
                        template_id=template.template_id,
                        name=template.name,
                        version=template.version,
                        description=template.description,
                        field_count=len(template.fields),
                        fields=[f.field_id for f in template.fields],
                    )
                )
            except Exception as e:
                logger.warning(f"Could not load template '{template_id}': {e}")

        return summaries

    @classmethod
    def register_in_memory(cls, template: FormTemplate) -> None:
        """Register or override a template directly in memory (useful for testing)."""
        cls._cache[template.template_id] = template

    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached templates."""
        cls._cache.clear()
