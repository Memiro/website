"""Bounds of the input, one source for the forms that declare them (§13.6)."""

from decimal import Decimal

# Input bounds, not the production limit: what the studio takes on is admin
# data in ``PricingSettings``. These only keep a hand-written request from
# asking for a kilometre of mirror.
MIN_SIDE_MM = 1
MAX_SIDE_MM = 10_000

# The dictionary of one category is a screen of the admin; a request naming
# more choices than that is not a configuration.
MAX_SELECTIONS = 50

# A numeric attribute counts cutouts and the like. The bound is an input
# bound, not a business rule: without it a hand-written ``1E+999999999``
# reaches the arithmetic and dies there as ``decimal.Overflow``.
MAX_QUANTITY = Decimal(10_000)

MAX_INQUIRY_ITEMS = 20
MIN_NAME_LENGTH = 1
MAX_NAME_LENGTH = 100
MIN_PHONE_LENGTH = 1
MAX_PHONE_LENGTH = 32
MAX_EMAIL_LENGTH = 254
MAX_COMMENT_LENGTH = 2_000

# The description of a product card: a paragraph the owner writes, bounded by
# the column that stores it.
MAX_DESCRIPTION_LENGTH = 2_000
MAX_WISH_LENGTH = 1_000

# The dictionary of one attribute is a card of the admin: the rows the owner
# scrolls through, not a catalogue of its own.
MAX_ATTRIBUTE_VALUES = 50

# Dependence between attributes is read by the customer as "this appears when
# that is chosen"; a chain no one can follow is not a form.
MAX_ATTRIBUTE_PARENTS = 10

# An input bound on a tariff, not a business rule: the studio's own prices are
# far below it, and without it a hand-written ``1E+999999999`` reaches the
# arithmetic and dies there as ``decimal.Overflow``.
MAX_RATE_AMOUNT = Decimal(10_000_000)

# The surcharge table is a card of the admin: a handful of steps at which the
# studio's production changes, not a price list of its own.
MAX_SIZE_SURCHARGES = 20

# Input bounds on the calculation parameters, not business rules: what the
# studio charges and takes on is the owner's data.
MAX_SURCHARGE_FACTOR = Decimal(100)
MAX_AREA_M2 = Decimal(100)
MAX_ORDER_TOTAL = Decimal(10_000_000)
