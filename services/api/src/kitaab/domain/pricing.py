"""Price calculator. The server is the source of truth; the app runs the same
rules for its instant calculator, and both are tested against
packages/contracts/pricing_vectors.json.

    goods = ceil_to_rupee((pages * rate[paper] + binding_fee[binding]) * copies + sourcing_cost)
    total = goods + delivery_fee[zone] + (cod_fee if payment is COD)

All amounts are integer paisa. `rate[paper]` comes from the highest volume
bracket whose `min_printed_pages` is at most `pages * copies` (D-014).
"""

from pydantic import BaseModel, Field, model_validator

from kitaab.domain.enums import Binding, Paper, PaymentMethod


class PricingError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class VolumeBracket(BaseModel):
    min_printed_pages: int = Field(ge=1)
    rate_per_page_paisa: int = Field(ge=0)


class PaperRate(BaseModel):
    rate_per_page_paisa: int = Field(ge=0)
    brackets: list[VolumeBracket] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_brackets(self) -> "PaperRate":
        starts = [b.min_printed_pages for b in self.brackets]
        if len(starts) != len(set(starts)):
            raise ValueError("volume brackets must have distinct min_printed_pages")
        return self


class BindingRate(BaseModel):
    fee_paisa: int = Field(ge=0)
    max_pages: int | None = Field(default=None, ge=1)


class PricingRules(BaseModel):
    """The JSON document stored in `pricing_configs.config`."""

    papers: dict[Paper, PaperRate]
    bindings: dict[Binding, BindingRate]
    delivery_fees_paisa: dict[str, int] = Field(
        description="Delivery fee per courier zone code, in paisa"
    )
    cod_fee_paisa: int = Field(ge=0)
    max_copies: int = Field(default=50, ge=1)

    @model_validator(mode="after")
    def _complete(self) -> "PricingRules":
        missing: list[str] = [p for p in Paper if p not in self.papers]
        missing += [b for b in Binding if b not in self.bindings]
        if missing:
            raise ValueError(f"pricing config is missing: {', '.join(missing)}")
        if any(fee < 0 for fee in self.delivery_fees_paisa.values()):
            raise ValueError("delivery fees cannot be negative")
        return self


class PriceInput(BaseModel):
    pages: int
    paper: Paper
    binding: Binding
    copies: int = 1
    zone: str
    payment_method: PaymentMethod | None = None
    sourcing_cost_paisa: int = 0
    goods_override_paisa: int | None = None


class PriceBreakdown(BaseModel):
    """Every line of a price, stored with each order as a snapshot."""

    config_version: int
    pages: int
    copies: int
    paper: Paper
    binding: Binding
    printed_pages: int
    rate_per_page_paisa: int
    printing_paisa: int
    binding_paisa: int
    sourcing_cost_paisa: int
    goods_before_rounding_paisa: int
    rounding_paisa: int
    calculated_goods_paisa: int
    goods_override: bool
    goods_paisa: int
    delivery_zone: str
    delivery_paisa: int
    payment_method: PaymentMethod | None
    cod_fee_paisa: int
    total_paisa: int


def ceil_to_rupee(paisa: int) -> int:
    """Round up to the next whole rupee (100 paisa)."""
    return -(-paisa // 100) * 100


def rate_for(paper: PaperRate, printed_pages: int) -> int:
    rate = paper.rate_per_page_paisa
    best_start = 0
    for bracket in paper.brackets:
        if best_start < bracket.min_printed_pages <= printed_pages:
            best_start = bracket.min_printed_pages
            rate = bracket.rate_per_page_paisa
    return rate


def calculate(rules: PricingRules, version: int, item: PriceInput) -> PriceBreakdown:
    if item.pages < 1:
        raise PricingError("INVALID_PAGES", "Page count must be at least 1")
    if not 1 <= item.copies <= rules.max_copies:
        raise PricingError("INVALID_COPIES", f"Copies must be between 1 and {rules.max_copies}")
    binding = rules.bindings[item.binding]
    if binding.max_pages is not None and item.pages > binding.max_pages:
        raise PricingError(
            "PAGES_EXCEED_BINDING_MAX",
            f"This binding supports at most {binding.max_pages} pages",
        )
    if item.zone not in rules.delivery_fees_paisa:
        raise PricingError("UNKNOWN_ZONE", "Delivery is not available for this city yet")
    if item.sourcing_cost_paisa < 0:
        raise PricingError("INVALID_SOURCING_COST", "Sourcing cost cannot be negative")
    if item.goods_override_paisa is not None and item.goods_override_paisa < 0:
        raise PricingError("INVALID_OVERRIDE", "Override price cannot be negative")

    printed_pages = item.pages * item.copies
    rate = rate_for(rules.papers[item.paper], printed_pages)
    printing = printed_pages * rate
    binding_total = binding.fee_paisa * item.copies
    before_rounding = printing + binding_total + item.sourcing_cost_paisa
    calculated_goods = ceil_to_rupee(before_rounding)
    goods = calculated_goods if item.goods_override_paisa is None else item.goods_override_paisa
    delivery = rules.delivery_fees_paisa[item.zone]
    cod_fee = rules.cod_fee_paisa if item.payment_method == PaymentMethod.COD else 0

    return PriceBreakdown(
        config_version=version,
        pages=item.pages,
        copies=item.copies,
        paper=item.paper,
        binding=item.binding,
        printed_pages=printed_pages,
        rate_per_page_paisa=rate,
        printing_paisa=printing,
        binding_paisa=binding_total,
        sourcing_cost_paisa=item.sourcing_cost_paisa,
        goods_before_rounding_paisa=before_rounding,
        rounding_paisa=calculated_goods - before_rounding,
        calculated_goods_paisa=calculated_goods,
        goods_override=item.goods_override_paisa is not None,
        goods_paisa=goods,
        delivery_zone=item.zone,
        delivery_paisa=delivery,
        payment_method=item.payment_method,
        cod_fee_paisa=cod_fee,
        total_paisa=goods + delivery + cod_fee,
    )


PLACEHOLDER_RULES = PricingRules(
    papers={
        Paper.LOCAL_WHITE: PaperRate(
            rate_per_page_paisa=200,
            brackets=[VolumeBracket(min_printed_pages=2000, rate_per_page_paisa=180)],
        ),
        Paper.IMPORTED_YELLOW: PaperRate(
            rate_per_page_paisa=275,
            brackets=[VolumeBracket(min_printed_pages=2000, rate_per_page_paisa=250)],
        ),
    },
    bindings={
        Binding.SOFTCOVER_PAPERBACK: BindingRate(fee_paisa=15_000, max_pages=800),
        Binding.PREMIUM_HARDCOVER: BindingRate(fee_paisa=50_000, max_pages=1200),
    },
    delivery_fees_paisa={"Z1": 20_000, "Z2": 25_000, "Z3": 35_000},
    cod_fee_paisa=5_000,
    max_copies=50,
)
"""Placeholder values seeded on first run. Replace before launch (OWNER_TODO.md)."""
