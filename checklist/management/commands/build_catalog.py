import csv
import gzip
import os
import shutil
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

USER_AGENT = "legochecklist (+https://github.com/jgoewert/legochecklist)"
DOWNLOAD_TIMEOUT_SECONDS = 120

# A download smaller than this fraction of the committed copy is treated as broken.
MINIMUM_DOWNLOAD_RATIO = 0.8

# Anything that can go wrong downloading or reading a file. Network errors are
# OSErrors, and truncated or corrupt gzip files raise EOFError or OSError.
DOWNLOAD_ERRORS = (
    CommandError,
    OSError,
    EOFError,
    ValueError,
    csv.Error,
    sqlite3.Error,
)

# Each table is loaded from the CSV of the same name, either compressed (.csv.gz)
# or not (.csv). Columns are matched by name, so any others in the files are ignored.
TABLES = {
    "sets": "set_num TEXT PRIMARY KEY, name TEXT",
    "inventories": "id INTEGER PRIMARY KEY, version INTEGER, set_num TEXT",
    "inventory_parts": (
        "inventory_id INTEGER, part_num TEXT, color_id INTEGER, "
        "quantity INTEGER, is_spare TEXT, img_url TEXT"
    ),
    "inventory_minifigs": "inventory_id INTEGER, fig_num TEXT, quantity INTEGER",
    "parts": "part_num TEXT PRIMARY KEY, name TEXT",
    "colors": "id INTEGER PRIMARY KEY, name TEXT, rgb TEXT",
}
INDEXES = (
    "CREATE INDEX inventories_set_num ON inventories (set_num)",
    "CREATE INDEX inventory_parts_inventory_id ON inventory_parts (inventory_id)",
    "CREATE INDEX inventory_minifigs_inventory_id ON inventory_minifigs (inventory_id)",
)


def find_csv(csv_dir, table):
    for path in (csv_dir / f"{table}.csv.gz", csv_dir / f"{table}.csv"):
        if path.is_file():
            return path
    raise CommandError(f"Missing {table}.csv or {table}.csv.gz in {csv_dir}")


def open_csv(path):
    opener = gzip.open if path.suffix == ".gz" else open
    return opener(path, "rt", newline="", encoding="utf-8")


def load_table(connection, csv_dir, table, definition):
    columns = [column.split()[0] for column in definition.split(", ")]
    path = find_csv(csv_dir, table)
    with open_csv(path) as csv_file:
        reader = csv.DictReader(csv_file)
        missing = set(columns) - set(reader.fieldnames or [])
        if missing:
            raise CommandError(f"{path} is missing columns: {sorted(missing)}")
        connection.execute(f"CREATE TABLE {table} ({definition})")
        placeholders = ", ".join("?" for _ in columns)
        cursor = connection.executemany(
            f"INSERT INTO {table} VALUES ({placeholders})",
            ([row[column] for column in columns] for row in reader),
        )
    return cursor.rowcount


def download_files(base_url, destination, committed_dir):
    """Downloads each table's .csv.gz file from base_url into destination."""
    for table in TABLES:
        name = f"{table}.csv.gz"
        path = destination / name
        request = Request(
            base_url.rstrip("/") + "/" + name, headers={"User-Agent": USER_AGENT}
        )
        with (
            urlopen(request, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response,
            open(path, "wb") as file,
        ):
            shutil.copyfileobj(response, file)

        committed = committed_dir / name
        if committed.is_file():
            minimum = committed.stat().st_size * MINIMUM_DOWNLOAD_RATIO
            if path.stat().st_size < minimum:
                raise CommandError(
                    f"Downloaded {name} is much smaller than {committed}"
                )


class Command(BaseCommand):
    help = "Builds the catalog database the site reads from the Rebrickable CSV files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-dir",
            type=Path,
            default=settings.CATALOG_CSV_DIR,
            help="Directory holding the CSV files, compressed or not.",
        )
        parser.add_argument(
            "--download",
            action="store_true",
            help=(
                "Build from the latest files on Rebrickable instead, falling back to "
                "--csv-dir if they can't be downloaded or read."
            ),
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="With --download, fail instead of falling back to --csv-dir.",
        )

    def handle(self, *args, csv_dir, download=False, strict=False, **options):
        if download:
            try:
                self.build_from_download(csv_dir)
                return
            except DOWNLOAD_ERRORS as exc:
                if strict:
                    raise CommandError(f"Could not use downloaded data: {exc}") from exc
                message = f"Could not use downloaded data ({exc}), so building from"
                self.stderr.write(self.style.WARNING(f"{message} {csv_dir}"))
        self.build(csv_dir)

    def build_from_download(self, committed_dir):
        url = settings.CATALOG_DOWNLOAD_URL
        self.stdout.write(f"Downloading from {url}")
        with tempfile.TemporaryDirectory() as directory:
            download_files(url, Path(directory), committed_dir)
            self.build(Path(directory))

    def build(self, csv_dir):
        database = Path(settings.CATALOG_DB)
        for table in TABLES:
            find_csv(csv_dir, table)

        # Build beside the target and swap it in, so a running site keeps a complete
        # catalog throughout and a failed build leaves the old one in place.
        temporary = database.with_name(f"{database.name}.tmp")
        temporary.unlink(missing_ok=True)
        try:
            with closing(sqlite3.connect(temporary)) as connection:
                connection.execute("PRAGMA journal_mode = OFF")
                connection.execute("PRAGMA synchronous = OFF")
                for table, definition in TABLES.items():
                    count = load_table(connection, csv_dir, table, definition)
                    self.stdout.write(f"{table}: {count} rows")
                for index in INDEXES:
                    connection.execute(index)
                connection.commit()
            os.replace(temporary, database)
        finally:
            temporary.unlink(missing_ok=True)
        self.stdout.write(self.style.SUCCESS(f"Built {database}"))
