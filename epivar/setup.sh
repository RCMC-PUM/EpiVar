#!/bin/bash
echo "----- Collect static files ------ "
python manage.py collectstatic --noinput

echo "----------- Apply migrations --------- "
python manage.py makemigrations cms users ontologies reference_genomes studies datasets analyses
python manage.py migrate

echo "----------- Add superuser --------- "
python manage.py createsuperuser --no-input

echo "----------- Run app --------- "
python -m gunicorn 'epivar.wsgi' --limit-request-field_size 8190 --limit-request-line 8190 --bind=0.0.0.0:8000 --log-level debug  --access-logfile /app/epivar/gunicorn.log  --error-logfile /app/epivar/gunicorn_error.log --timeout 120 --workers=1
