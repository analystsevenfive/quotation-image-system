"""Quotation and matching data models."""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from app.models.product import Product


class MatchStatus(str, Enum):
    MATCHED = "matched"
    NEEDS_REVIEW = "needs_review"
    MISSING = "missing"
    MANUAL = "manual"


class MatchMethod(str, Enum):
    EXACT_SKU = "exact_sku"
    WINSPEED = "winspeed"
    NORMALIZED_SKU = "normalized_sku"
    MODEL = "model"
    MANUAL = "manual"


class BoundingBox(BaseModel):
    """Bounding box coordinates [x0, y0, x1, y1] in PDF points."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)


class QuotationItem(BaseModel):
    """Extracted item from a quotation PDF."""

    item_number: int
    page_number: int
    description: str
    detected_sku: Optional[str] = None
    detected_model: Optional[str] = None
    bbox: BoundingBox
    image_bbox: Optional[BoundingBox] = None

    # Matching state
    matched_product: Optional[Product] = None
    candidate_products: List[Product] = Field(default_factory=list)
    match_status: MatchStatus = MatchStatus.MISSING
    match_method: Optional[MatchMethod] = None
    match_confidence: float = 0.0

    # Image insertion state
    selected_image_url: Optional[str] = None
    image_inserted: bool = False
    error_message: Optional[str] = None


class ProcessingReport(BaseModel):
    """Summary report of quotation processing."""

    source_file: str
    output_file: Optional[str] = None
    total_items: int = 0
    matched_count: int = 0
    needs_review_count: int = 0
    missing_count: int = 0
    images_inserted_count: int = 0
    items: List[QuotationItem] = Field(default_factory=list)
