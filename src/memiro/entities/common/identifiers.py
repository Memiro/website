from uuid import UUID

# One alias per kind of identifier, so a signature says what it takes; the
# runtime type is the plain UUID (§4).
type ProductId = UUID
type VariantId = UUID
type CategoryId = UUID
type AttributeId = UUID
type AttributeValueId = UUID
type PricingSettingsId = UUID
