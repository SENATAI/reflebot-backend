#!/bin/bash
set -euo pipefail

uv run celery -A reflebot.celery_app:celery_app worker --loglevel=info
