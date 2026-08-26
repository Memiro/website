from sqlalchemy.orm import registry

# The single registry for imperative mapping; alembic autogenerate reads its
# metadata, so every domain table must be declared against it.
mapper_registry = registry()
