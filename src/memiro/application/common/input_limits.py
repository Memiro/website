"""Bounds of the input, one source for the forms that declare them (§13.6)."""

# Input bounds, not the production limit: what the studio takes on is admin
# data in ``PricingSettings``. These only keep a hand-written request from
# asking for a kilometre of mirror.
MIN_SIDE_MM = 1
MAX_SIDE_MM = 10_000

# The dictionary of one category is a screen of the admin; a request naming
# more choices than that is not a configuration.
MAX_SELECTIONS = 50

MAX_INQUIRY_ITEMS = 20
MIN_NAME_LENGTH = 1
MAX_NAME_LENGTH = 100
MIN_PHONE_LENGTH = 1
MAX_PHONE_LENGTH = 32
MAX_EMAIL_LENGTH = 254
MAX_COMMENT_LENGTH = 2_000
MAX_WISH_LENGTH = 1_000
