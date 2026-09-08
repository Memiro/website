from memiro.entities.catalog.attribute.rate import Unit

# The unit words stand inside the formulas of the workbook: a sheet says "за
# м²" and the sum column asks whether it does. Renaming one without the other
# leaves a book that quietly charges nothing.
UNIT_LABELS = {
    Unit.SQUARE_METER: "за м²",
    Unit.LINEAR_METER: "за пог. м",
    Unit.PIECE: "за штуку",
    Unit.FACTOR: "коэффициент",
}

YES = "да"
NO = "нет"


def key_of(attribute_name: str, value_name: str) -> str:
    """Build the dictionary key the calculation sheet looks a tariff up by."""
    return f"{attribute_name} | {value_name}"
