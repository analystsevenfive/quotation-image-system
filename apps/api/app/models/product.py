"""Product master data models."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ImageStatus(str, Enum):
    AVAILABLE = "available"
    MISSING = "missing"
    BROKEN = "broken"


class Product(BaseModel):
    """Represents a product from the Product Master."""

    id: Optional[int] = None
    good_id: Optional[str] = None
    sku: str
    winspeed: Optional[str] = None
    model: Optional[str] = None
    title: Optional[str] = None
    good_bill_name: Optional[str] = None
    product_url: Optional[str] = None
    image_url: Optional[str] = None
    image_status: ImageStatus = ImageStatus.AVAILABLE

