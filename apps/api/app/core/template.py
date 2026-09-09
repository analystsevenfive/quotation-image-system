"""Quotation layout template definitions."""

from typing import List, Optional
from pydantic import BaseModel, Field


class QuotationTemplate(BaseModel):
    """Layout rules and geometry boundaries for quotation PDFs."""

    name: str = "standard_default"
    description: Optional[str] = "Standard quotation layout with 5 columns"

    # Column boundaries (in PDF points, 72 pt/inch)
    item_col_x0: float = 25.0
    item_col_x1: float = 60.0

    desc_col_x0: float = 60.0
    desc_col_x1: float = 410.0

    qty_col_x0: float = 413.0
    qty_col_x1: float = 455.0

    price_col_x0: float = 458.0
    price_col_x1: float = 515.0

    net_price_col_x0: float = 518.0
    net_price_col_x1: float = 580.0

    # Header and footer boundaries
    header_keywords: List[str] = Field(
        default_factory=lambda: ["ITEM", "DESCRIPTION", "QTY", "PRICE", "NET PRICE", "NET"]
    )
    footer_keywords: List[str] = Field(
        default_factory=lambda: [
            "TOTAL",
            "SUBTOTAL",
            "SUB TOTAL",
            "REMARK",
            "TERMS",
            "CONDITIONS",
            "SIGNATURE",
            "NOTE",
            "GRAND TOTAL",
            "BAHT",
        ]
    )
    default_header_bottom_y: float = 278.0
    default_footer_top_y: float = 600.0

    # Image insertion constraints
    # Images reside on the right-side portion of the DESCRIPTION column
    image_max_width: float = 110.0
    image_max_height: float = 100.0
    image_slot_center_x: float = 350.0
    image_min_slot_height: float = 0.0  # 0.0 for strict row bounds; >0 for expansion in sparse columns
    image_right_margin: float = 11.0  # clearance before qty_col_x0 (413.0 - 11.0 = 402.0)
    image_top_margin: float = 3.0
    image_bottom_margin: float = 3.0
    min_row_height_for_image: float = 20.0


DEFAULT_TEMPLATE = QuotationTemplate()

SEVEN_FIVE_TEMPLATE = QuotationTemplate(
    name="seven_five_distributor",
    description="Seven Five Distributor quotation layout with centered image slot",
    item_col_x0=25.0,
    item_col_x1=60.0,
    desc_col_x0=60.0,
    desc_col_x1=410.0,
    qty_col_x0=413.0,
    qty_col_x1=455.0,
    price_col_x0=458.0,
    price_col_x1=515.0,
    net_price_col_x0=518.0,
    net_price_col_x1=580.0,
    default_header_bottom_y=278.0,
    default_footer_top_y=588.0,
    image_max_width=110.0,
    image_max_height=100.0,
    image_slot_center_x=350.0,
    image_min_slot_height=95.0,
    image_right_margin=11.0,
    image_top_margin=3.0,
    image_bottom_margin=3.0,
)
