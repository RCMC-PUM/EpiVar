#!/usr/bin/sh
poetry run python -m celery -A epivar worker --loglevel="INFO"