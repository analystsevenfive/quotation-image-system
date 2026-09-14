"""Product matching engine implementing 5-tier matching priority."""

from collections import defaultdict
import re
from typing import Dict, List, Optional, Tuple

from app.models.product import Product
from app.models.quotation import MatchMethod, MatchStatus
from app.services.matching.normalizer import extract_model_from_sku, normalize_sku, normalize_bill_name


class MatchResult:
    """Result of matching a detected item against the Product Master."""

    def __init__(
        self,
        status: MatchStatus,
        method: Optional[MatchMethod] = None,
        confidence: float = 0.0,
        product: Optional[Product] = None,
        candidates: Optional[List[Product]] = None,
    ):
        self.status = status
        self.method = method
        self.confidence = confidence
        self.product = product
        self.candidates = candidates or []


class ProductMatcher:
    """
    Matches detected quotation strings against the Product Master catalog.
    
    Strict Priority:
    0. Saved Manual Mapping
    1. Exact SKU
    2. Exact winspeed
    3. Normalized SKU
    4. Good Bill Name (Full billing name match)
    5. Model
    6. Manual review (needs_review or missing)
    
    Rule: Never auto-accept ambiguous matches.
    """

    def __init__(self, products: List[Product], mapping_store=None):
        self.products = products
        self.mapping_store = mapping_store
        self._by_id = {p.id: p for p in products}
        self._exact_sku_index: Dict[str, List[Product]] = defaultdict(list)
        self._exact_winspeed_index: Dict[str, List[Product]] = defaultdict(list)
        self._normalized_sku_index: Dict[str, List[Product]] = defaultdict(list)
        self._exact_bill_name_index: Dict[str, List[Product]] = defaultdict(list)
        self._normalized_bill_name_index: Dict[str, List[Product]] = defaultdict(list)
        self._model_index: Dict[str, List[Product]] = defaultdict(list)

        self._build_indices()

    def _build_indices(self) -> None:
        for p in self.products:
            if p.sku:
                raw_sku = p.sku.strip()
                self._exact_sku_index[raw_sku].append(p)
                norm_sku = normalize_sku(raw_sku)
                self._normalized_sku_index[norm_sku].append(p)

            if p.winspeed:
                raw_ws = p.winspeed.strip()
                self._exact_winspeed_index[raw_ws].append(p)

            if p.good_bill_name:
                raw_bn = p.good_bill_name.strip()
                if raw_bn and raw_bn != "0":
                    self._exact_bill_name_index[raw_bn].append(p)
                    norm_bn = normalize_bill_name(raw_bn)
                    if norm_bn:
                        self._normalized_bill_name_index[norm_bn].append(p)

            # Model indexing
            model_val = p.model or extract_model_from_sku(p.sku)
            if model_val:
                norm_model = normalize_sku(model_val)
                self._model_index[norm_model].append(p)
            # Imported model fields can be truncated (e.g. 331 instead of 331.044).
            # Retain the full model encoded after a structured catalog brand prefix.
            if re.match(r"^[A-Z]+[0-9]+-", normalize_sku(p.sku)):
                sku_model = extract_model_from_sku(p.sku)
                if sku_model and normalize_sku(sku_model) != normalize_sku(model_val):
                    self._model_index[normalize_sku(sku_model)].append(p)

    def match(
        self,
        detected_value: Optional[str],
        detected_model: Optional[str] = None,
        description: Optional[str] = None,
    ) -> MatchResult:
        """
        Attempts to match the detected string using the priority hierarchy:
        0. Saved Manual Mapping
        1. Exact SKU
        2. Exact winspeed
        3. Normalized SKU
        4. Good Bill Name
        5. Model
        6. Manual review (needs_review or missing)
        """
        if not detected_value and not detected_model and not description:
            return MatchResult(status=MatchStatus.MISSING, confidence=0.0)

        raw_val = (detected_value or "").strip()
        norm_val = normalize_sku(raw_val)

        # 0. Saved Manual Mapping (Priority 0)
        if self.mapping_store:
            mapped_id = self.mapping_store.get(raw_val) or (self.mapping_store.get(norm_val) if norm_val else None)
            if mapped_id is not None and mapped_id in self._by_id:
                return MatchResult(
                    status=MatchStatus.MATCHED,
                    method=MatchMethod.MANUAL,
                    confidence=1.0,
                    product=self._by_id[mapped_id],
                )

        # 1. Exact SKU
        if raw_val and raw_val in self._exact_sku_index:
            matches = self._exact_sku_index[raw_val]
            if len(matches) == 1:
                return MatchResult(
                    status=MatchStatus.MATCHED,
                    method=MatchMethod.EXACT_SKU,
                    confidence=1.0,
                    product=matches[0],
                )
            # Ambiguous exact matches
            return MatchResult(
                status=MatchStatus.NEEDS_REVIEW,
                method=MatchMethod.EXACT_SKU,
                confidence=0.85,
                candidates=matches,
            )

        # 2. Exact Winspeed
        if raw_val and raw_val in self._exact_winspeed_index:
            matches = self._exact_winspeed_index[raw_val]
            if len(matches) == 1:
                return MatchResult(
                    status=MatchStatus.MATCHED,
                    method=MatchMethod.WINSPEED,
                    confidence=0.95,
                    product=matches[0],
                )
            return MatchResult(
                status=MatchStatus.NEEDS_REVIEW,
                method=MatchMethod.WINSPEED,
                confidence=0.80,
                candidates=matches,
            )

        # 3. Normalized SKU
        if norm_val and norm_val in self._normalized_sku_index:
            matches = self._normalized_sku_index[norm_val]
            if len(matches) == 1:
                return MatchResult(
                    status=MatchStatus.MATCHED,
                    method=MatchMethod.NORMALIZED_SKU,
                    confidence=0.90,
                    product=matches[0],
                )
            return MatchResult(
                status=MatchStatus.NEEDS_REVIEW,
                method=MatchMethod.NORMALIZED_SKU,
                confidence=0.75,
                candidates=matches,
            )

        # 4. Good Bill Name Match (Full billing name match)
        bill_candidates = []
        if description:
            raw_desc = description.strip()
            norm_desc = normalize_bill_name(raw_desc)
            if raw_desc in self._exact_bill_name_index:
                bill_candidates = self._exact_bill_name_index[raw_desc]
            elif norm_desc in self._normalized_bill_name_index:
                bill_candidates = self._normalized_bill_name_index[norm_desc]
            else:
                first_line = raw_desc.split("\n")[0].strip()
                norm_first = normalize_bill_name(first_line)
                if norm_first in self._normalized_bill_name_index:
                    bill_candidates = self._normalized_bill_name_index[norm_first]
                elif len(norm_desc) >= 10:
                    for bname, prods in self._normalized_bill_name_index.items():
                        if len(bname) >= 10 and (norm_desc.startswith(bname) or bname.startswith(norm_desc)):
                            bill_candidates.extend(prods)
                    seen_ids = set()
                    unique_candidates = []
                    for cp in bill_candidates:
                        if cp.id not in seen_ids:
                            seen_ids.add(cp.id)
                            unique_candidates.append(cp)
                    bill_candidates = unique_candidates

        if not bill_candidates and raw_val:
            if raw_val in self._exact_bill_name_index:
                bill_candidates = self._exact_bill_name_index[raw_val]
            else:
                norm_raw_bill = normalize_bill_name(raw_val)
                if norm_raw_bill in self._normalized_bill_name_index:
                    bill_candidates = self._normalized_bill_name_index[norm_raw_bill]

        if bill_candidates:
            if len(bill_candidates) == 1:
                return MatchResult(
                    status=MatchStatus.MATCHED,
                    method=MatchMethod.GOOD_BILL_NAME,
                    confidence=0.88,
                    product=bill_candidates[0],
                )
            return MatchResult(
                status=MatchStatus.NEEDS_REVIEW,
                method=MatchMethod.GOOD_BILL_NAME,
                confidence=0.70,
                candidates=bill_candidates,
            )

        # 5. Model Match
        candidate_models = []
        if detected_model:
            candidate_models.append(normalize_sku(detected_model))
        if norm_val and norm_val not in candidate_models:
            candidate_models.append(norm_val)
        extracted = extract_model_from_sku(norm_val)
        if extracted and normalize_sku(extracted) not in candidate_models:
            candidate_models.append(normalize_sku(extracted))

        for cand in candidate_models:
            if cand and cand in self._model_index:
                matches = self._model_index[cand]
                if len(matches) == 1:
                    return MatchResult(
                        status=MatchStatus.MATCHED,
                        method=MatchMethod.MODEL,
                        confidence=0.80,
                        product=matches[0],
                    )
                # Ambiguous model matches must NEVER be auto-accepted
                return MatchResult(
                    status=MatchStatus.NEEDS_REVIEW,
                    method=MatchMethod.MODEL,
                    confidence=0.50,
                    candidates=matches,
                )

        # 5. Missing / Manual Review
        return MatchResult(status=MatchStatus.MISSING, confidence=0.0)
