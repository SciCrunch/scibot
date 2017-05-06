gunicorn -b localhost:5000 -n scibot -w 4 -t 600 --log-level debug server:app
