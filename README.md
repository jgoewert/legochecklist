# LEGO Checklist

A simple, printable checklist for pieces in a LEGO set written in Python/Django

Running at https://legochecklist.onrender.com/

Based on the PHP code from chkno.net

Licensed under the MIT License

## Running locally

You need Python 3.12 or newer.

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py build_catalog
python manage.py runserver
```

## Updating the data

Set and part data comes from [Rebrickable's downloads page](https://rebrickable.com/downloads/),
stored compressed in `data/`. Only `sets`, `inventories`, `inventory_parts`,
`inventory_minifigs`, `parts` and `colors` are used.

To update it, replace those `.csv.gz` files, commit them, and run
`python manage.py build_catalog`. That reads the files into `catalog.sqlite3`, which
is what the site uses, and swaps the new catalog in once it is complete. The catalog
itself is not committed.

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

Use `pip install -r requirements.txt && python manage.py build_catalog` as the build
step and `gunicorn legochecklist.wsgi` as the start command, with `SECRET_KEY` set for
both. The site returns a 503 until a catalog has been built.
`DEBUG` is off by default. Set `ALLOWED_HOSTS` to your hostnames; Render's own
hostname is added automatically. See `.env.example` for details.
