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
MAX_WISH_LENGTH = 1_000
