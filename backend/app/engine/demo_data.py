"""Fictional demo brand configuration for local testing and demonstration.
Clearly labeled as demo data.
"""

from ..models.rules import (
    BrandRulesConfig,
    ProhibitedTermRule,
    PreferredWordingRule,
    ApprovedFact,
    RequiredDisclaimerRule,
    Severity,
)

DEMO_BRAND_RULES = BrandRulesConfig(
    brand_name="NovaSound Audio (Demo Data)",
    description="NovaSound Audio is a premier acoustic engineering brand dedicated to studio-grade fidelity, Active Acoustic Isolation™, and aerospace-grade construction.",
    voice_and_tone="Sophisticated, authoritative, acoustically technical, and refined. Never colloquial, combative, sensationalist, or cheapening.",
    is_demo=True,
    prohibited_terms=[
        ProhibitedTermRule(
            id="rule-prohib-01",
            term_or_pattern="cheap headphones",
            is_regex=False,
            case_sensitive=False,
            severity=Severity.critical,
            explanation="NovaSound is positioned as a premium acoustic brand; never refer to products as 'cheap'.",
            suggested_replacement="accessible high-fidelity audio",
        ),
        ProhibitedTermRule(
            id="rule-prohib-02",
            term_or_pattern="unbreakable",
            is_regex=False,
            case_sensitive=False,
            severity=Severity.critical,
            explanation="Absolute durability claims like 'unbreakable' create liability and violate advertising standards.",
            suggested_replacement="aerospace-grade aluminum durability",
        ),
        ProhibitedTermRule(
            id="rule-prohib-03",
            term_or_pattern=r"\bkills\s+the\s+competition\b",
            is_regex=True,
            case_sensitive=False,
            severity=Severity.critical,
            explanation="Aggressive or derogatory competitive phrases violate brand conduct standards.",
            suggested_replacement="leads the industry in acoustic clarity",
        ),
    ],
    preferred_wording=[
        PreferredWordingRule(
            id="rule-pref-01",
            avoid_term="earbuds",
            preferred_term="in-ear acoustic monitors",
            case_sensitive=False,
            severity=Severity.info,
            explanation="NovaSound brand voice specifies technical acoustic nomenclature over colloquial terms.",
        ),
        PreferredWordingRule(
            id="rule-pref-02",
            avoid_term="noise cancellation",
            preferred_term="Active Acoustic Isolation™",
            case_sensitive=False,
            severity=Severity.warning,
            explanation="Always cite our trademarked Active Acoustic Isolation™ technology rather than generic ANC terms.",
        ),
    ],
    approved_facts=[
        ApprovedFact(
            id="fact-01",
            entity="NovaSound Apex Wireless",
            attribute="MSRP Price",
            approved_value="$299",
            context_keywords=["price", "cost", "costs", "msrp", "retail", "$"],
            conflicting_patterns=[
                r"\$(?!299\b)\d+(?:,\d{3})*(?:\.\d{2})?",
                r"\b(?:under\s+\$200|only\s+\$199|\$349|\$399)\b",
            ],
            severity=Severity.critical,
            explanation="The approved MSRP for NovaSound Apex Wireless is $299. Outdated or inaccurate pricing violates brand pricing policy.",
        ),
        ApprovedFact(
            id="fact-02",
            entity="NovaSound Apex Wireless",
            attribute="Battery Playback",
            approved_value="40 hours",
            context_keywords=["battery", "playback", "hours", "charge", "runtime"],
            conflicting_patterns=[
                r"\b(?:50|60|70|80|100)\s*hours?\b",
                r"\b(?:10|15|20|24|30)\s*hours?\b",
            ],
            severity=Severity.critical,
            explanation="Tested and certified playback duration is 40 hours with Active Acoustic Isolation™ enabled.",
        ),
        ApprovedFact(
            id="fact-03",
            entity="NovaSound Pulse Earphones",
            attribute="Water Resistance",
            approved_value="IPX7 rating",
            context_keywords=["water", "waterproof", "water-resistant", "ipx", "submersion"],
            conflicting_patterns=[
                r"\bIPX8\b",
                r"\bIP68\b",
                r"\b100%\s*waterproof\b",
                r"\bfully\s+waterproof\b",
            ],
            severity=Severity.critical,
            explanation="NovaSound Pulse Earphones are IPX7 rated. Stating '100% waterproof' or 'IPX8' contradicts official technical specifications.",
        ),
    ],
    required_disclaimers=[
        RequiredDisclaimerRule(
            id="disclaimer-01",
            trigger_pattern=r"\b(?:lifetime\s+warranty|guaranteed\s+forever)\b",
            trigger_description="Mentions lifetime warranty or indefinite guarantee",
            required_disclaimer_text="*Subject to NovaSound Limited Lifetime Warranty Terms and fair usage policy.",
            case_sensitive=False,
            severity=Severity.warning,
            explanation="Warranty claims require standard terms disclosure to prevent misleading consumers.",
        ),
        RequiredDisclaimerRule(
            id="disclaimer-02",
            trigger_pattern=r"\b(?:hearing\s+protection|blocks\s+all\s+noise|protects?\s+against\s+hearing\s+loss)\b",
            trigger_description="Claims medical, occupational, or total noise protection",
            required_disclaimer_text="*NovaSound products are consumer audio devices, not OSHA-certified hearing protection equipment.",
            case_sensitive=False,
            severity=Severity.warning,
            explanation="Health and occupational hearing claims require statutory non-medical device disclosure.",
        ),
    ],
)
