# LEGO Checklist

A simple, printable checklist for pieces in a LEGO set written in Python/Django

Running at https://legochecklist.onrender.com/

Based on the PHP code from chkno.net

Licensed under the MIT License

Set and part data is sourced from [Rebrickable](https://rebrickable.com/).

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

`python manage.py build_catalog` reads the files into `catalog.sqlite3`, which is what
the site uses, and swaps the new catalog in once it is complete. The catalog itself is
not committed.

`python manage.py build_catalog --download` builds from the latest files on Rebrickable
instead, which are updated daily. If they can't be downloaded or read, it warns and
builds from `data/`; add `--strict` to fail instead. The deployed site builds this way,
so `data/` is only a fallback and for tests. Refresh it occasionally by replacing the
files and committing them.

### Daily updates

The *Refresh data* GitHub Action runs every day at 08:30 UTC, after Rebrickable's
update. It downloads the latest files, runs the tests against them, and if they pass,
calls the `RENDER_DEPLOY_HOOK_URL` repository secret to redeploy the site, whose build
downloads the files again. If the download or the tests fail, nothing is deployed and
the site keeps the previous day's data. It can also be run by hand from the Actions tab.

GitHub turns off scheduled workflows in a public repository after 60 days without any
activity, and emails a warning first. Re-enable it from the Actions tab.

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

Use `pip install -r requirements.txt && python manage.py build_catalog --download` as
the build step and `gunicorn legochecklist.wsgi` as the start command, with
`SECRET_KEY` set for both. The site returns a 503 until a catalog has been built.
`DEBUG` is off by default. Set `ALLOWED_HOSTS` to your hostnames; Render's own
hostname is added automatically. See `.env.example` for details.
