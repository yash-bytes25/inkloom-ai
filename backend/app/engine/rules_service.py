"""Brand Guidelines Service
========================
Manages the active brand governance configuration in local demo memory.
Allows dynamic modification of brand identity, prohibited terminology,
preferred wording, approved facts, required disclaimers, and voice & tone.
Supports restoring the pristine NovaSound Audio demo configuration at any time.
"""

from typing import Optional
from ..models.rules import BrandRulesConfig
from .demo_data import DEMO_BRAND_RULES


class BrandRulesService:
    """In-memory brand guidelines management service."""

    def __init__(self):
        # Initialize with deep copy of fictional demo brand
        self._active_rules: BrandRulesConfig = DEMO_BRAND_RULES.model_copy(deep=True)

    def get_active_rules(self) -> BrandRulesConfig:
        """Retrieve the currently active brand guidelines configuration."""
        return self._active_rules.model_copy(deep=True)

    def update_rules(self, updated_rules: BrandRulesConfig) -> BrandRulesConfig:
        """Update active brand rules with user configuration.

        Validates all rules and marks demo flag accordingly.
        """
        # If the user changed the brand name or rules, flag that it's user-customized
        if updated_rules.brand_name != DEMO_BRAND_RULES.brand_name:
            updated_rules.is_demo = False

        self._active_rules = updated_rules.model_copy(deep=True)
        return self.get_active_rules()

    def reset_to_demo(self) -> BrandRulesConfig:
        """Restore pristine NovaSound Audio demo configuration."""
        self._active_rules = DEMO_BRAND_RULES.model_copy(deep=True)
        return self.get_active_rules()


# Global singleton instance
rules_service = BrandRulesService()


def get_active_brand_rules() -> BrandRulesConfig:
    """Utility function to access current active brand guidelines."""
    return rules_service.get_active_rules()
