#!/bin/bash
uv run alembic revision -m "init tables" --autogenerate
uv run alembic upgrade head
