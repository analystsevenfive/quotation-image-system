import sys
from pathlib import Path

# Ensure apps/api is in sys.path
api_dir = Path(__file__).resolve().parent.parent.parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from tests.fixtures.generate_sample_pdf import (
    create_test_image,
    generate_quotation_pdf,
)
from tests.fixtures.sample_products import get_sample_products

__all__ = [
    "get_sample_products",
    "generate_quotation_pdf",
    "create_test_image",
]
