"""Bounds of the input, one source for the forms that declare them (§13.6)."""

# Input bounds, not the production limit: what the studio takes on is admin
# data in ``PricingSettings``. These only keep a hand-written request from
# asking for a kilometre of mirror.
MIN_SIDE_MM = 1
MAX_SIDE_MM = 10_000

# The dictionary of one category is a screen of the admin; a request naming
# more choices than that is not a configuration.
MAX_SELECTIONS = 50
