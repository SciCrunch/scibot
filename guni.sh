gunicorn -b localhost:5000 -n scibot -w 1 --log-level debug server:app
