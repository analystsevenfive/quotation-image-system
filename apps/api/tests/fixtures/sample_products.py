from pathlib import Path
import sys

api_dir = Path(__file__).resolve().parent.parent.parent
if str(api_dir) not in sys.path:
    sys.path.insert(0, str(api_dir))

from app.models.product import ImageStatus, Product


def get_sample_products() -> list:
    """Returns a representative list of test products covering all matching scenarios."""
    return [
        Product(
            id=1,
            good_id="1656",
            sku="BER1-BMCFP4",
            winspeed="BER1-BMCFP4",
            model="BMCFP4",
            product_url="https://www.sevenfive.co.th/products/ber1-bmcfp4",
            image_url="https://cdn.shopify.com/s/files/1/0000/products/BER1-BMCFP4.jpg",
            image_status=ImageStatus.AVAILABLE,
        ),
        Product(
            id=2,
            good_id="2042",
            sku="CSHL550",
            winspeed="CSHL550",
            model="CSHL550",
            product_url="https://www.sevenfive.co.th/products/cshl550",
            image_url="https://cdn.shopify.com/s/files/1/0000/products/CSHL550.jpg",
            image_status=ImageStatus.AVAILABLE,
        ),
        Product(
            id=3,
            good_id="3110",
            sku="DB-CW76-DRG",
            winspeed="DB-CW76-DRG",
            model="CW76-DRG",
            product_url="https://www.sevenfive.co.th/products/db-cw76-drg",
            image_url="https://cdn.shopify.com/s/files/1/0000/products/DB-CW76-DRG.png",
            image_status=ImageStatus.AVAILABLE,
        ),
        Product(
            id=4,
            good_id="4521",
            sku="DB-PP120-GY",
            winspeed="DB-PP120-GY",
            model="PP120-GY",
            product_url="https://www.sevenfive.co.th/products/db-pp120-gy",
            image_url=None,  # Missing image URL scenario
            image_status=ImageStatus.MISSING,
        ),
        # Two products with different SKUs sharing the same model to test ambiguous model handling
        Product(
            id=5,
            good_id="5001",
            sku="BRAND-A-MOD100",
            winspeed="WS-A-100",
            model="MOD100",
            image_url="https://cdn.shopify.com/s/files/1/0000/products/MOD100-A.jpg",
        ),
        Product(
            id=6,
            good_id="5002",
            sku="BRAND-B-MOD100",
            winspeed="WS-B-100",
            model="MOD100",
            image_url="https://cdn.shopify.com/s/files/1/0000/products/MOD100-B.jpg",
        ),
    ]
