"""CLI tool for processing quotation PDFs in Phase 1."""

import argparse
import json
from pathlib import Path
import sys

from app.models.product import Product
from app.services.pipeline import QuotationPipeline


def load_products_file(path: Path) -> list:
    """Loads product catalog from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        return [Product(**item) for item in data]


def main():
    parser = argparse.ArgumentParser(
        description="Quotation Image Automation System - PDF Engine (Phase 1)"
    )
    parser.add_argument("pdf_path", type=str, help="Path to input quotation PDF")
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Path for output PDF with images (defaults to <name>_with_images.pdf)",
    )
    parser.add_argument(
        "-p",
        "--products",
        type=str,
        default=None,
        help="Path to JSON file containing Product Master catalog",
    )

    args = parser.parse_args()

    input_path = Path(args.pdf_path)
    if not input_path.is_file():
        print(f"Error: Input PDF file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_name(f"{input_path.stem}_with_images.pdf")
    )

    products = []
    if args.products:
        prod_path = Path(args.products)
        if not prod_path.is_file():
            print(f"Error: Products file not found: {prod_path}", file=sys.stderr)
            sys.exit(1)
        products = load_products_file(prod_path)
    else:
        print("Note: No products file specified. Running with empty catalog.")

    pipeline = QuotationPipeline(products=products)
    print(f"Processing '{input_path}'...")

    try:
        report = pipeline.process(input_path, output_path=output_path)
        print("\n--- Quotation Processing Report ---")
        print(f"Total Items:     {report.total_items}")
        print(f"Matched:         {report.matched_count}")
        print(f"Needs Review:    {report.needs_review_count}")
        print(f"Missing:         {report.missing_count}")
        print(f"Images Inserted: {report.images_inserted_count}")
        print(f"Output saved to: {output_path}")

        for item in report.items:
            status_symbol = "OK" if item.match_status == "matched" else item.match_status.upper()
            print(
                f"  [{status_symbol}] Item #{item.item_number}: SKU='{item.detected_sku}' "
                f"Status={item.match_status} (Method={item.match_method}) "
                f"ImageInserted={item.image_inserted}"
            )
            if item.error_message:
                print(f"      Warning: {item.error_message}")

    except Exception as e:
        print(f"\nFailed to process quotation: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
