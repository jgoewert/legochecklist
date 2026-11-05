# LEGO Checklist

A simple, printable checklist for pieces in a LEGO set written in Python/Django

Running at https://legochecklist.onrender.com/

Based on the PHP code from chkno.net

Licensed under the MIT License

## Running locally

You need Python 3.12 or newer and the CSV files from
[Rebrickable's downloads page](https://rebrickable.com/downloads/), extracted into
`rebrickable_csv/all_downloads/`. Only `sets`, `inventories`, `inventory_parts`,
`parts` and `colors` are used.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py build_catalog
python manage.py runserver
```

## Updating the data

Replace the CSV files and run `python manage.py build_catalog` again. It reads the
files into `catalog.sqlite3`, which is what the site uses, and swaps the new catalog
in once it is complete. Neither the CSV files nor the catalog are committed.

## Tests

```sh
ruff check .
python manage.py test

# Page behaviour, which also needs Node.js
npm ci
npm test

```

`python manage.py test` also checks a known set against your built catalog, and
skips that test if there isn't one.

## Deploying

Install from `requirements.txt`, run `python manage.py build_catalog`, then run
`gunicorn legochecklist.wsgi` with `SECRET_KEY` set. The CSV files must be available
to the build step, and the site returns a 503 until a catalog has been built.
`DEBUG` is off by default. Set `ALLOWED_HOSTS` to your hostnames; Render's own
hostname is added automatically. See `.env.example` for details.
