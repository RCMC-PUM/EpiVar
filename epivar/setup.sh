#!/bin/bash
echo "----- Init buckets ------ "
python manage.py initialize_buckets

echo "----- Collect static files ------ "
python manage.py collectstatic --no-input

echo "----------- Apply migrations --------- "
python manage.py migrate --no-input

echo "----------- Initial reversion --------- "
python manage.py createinitialrevisions

echo "----------- Add superuser --------- "
python manage.py createsuperuser --no-input

echo "----------- Run app --------- "
python -m gunicorn 'epivar.wsgi' --limit-request-field_size 8190 \
                                 --limit-request-line 8190 \
                                 --bind=0.0.0.0:8000 \
                                 --log-level debug  \
                                 --access-logfile /app/epivar/gunicorn.log \
                                 --error-logfile /app/epivar/gunicorn_error.log \
                                 --timeout 120 \
                                 --workers=1
