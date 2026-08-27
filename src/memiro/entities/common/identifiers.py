from typing import NewType
from uuid import UUID

# Distinct types over one runtime UUID: a product id handed to an attribute
# gateway is a compile-time error, not a puzzling empty result.
ProductId = NewType("ProductId", UUID)
AttributeId = NewType("AttributeId", UUID)
AttributeValueId = NewType("AttributeValueId", UUID)
PricingSettingsId = NewType("PricingSettingsId", UUID)
