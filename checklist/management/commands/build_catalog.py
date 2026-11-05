import csv
import os
import sqlite3
from contextlib import closing
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

# Each table is loaded from the CSV of the same name. Columns are matched by name,
# so any other columns in the files are ignored.
TABLES = {
    "sets": "set_num TEXT PRIMARY KEY, name TEXT",
    "inventories": "id INTEGER PRIMARY KEY, version INTEGER, set_num TEXT",
    "inventory_parts": (
        "inventory_id INTEGER, part_num TEXT, color_id INTEGER, "
        "quantity INTEGER, is_spare TEXT, img_url TEXT"
    ),
    "parts": "part_num TEXT PRIMARY KEY, name TEXT",
    "colors": "id INTEGER PRIMARY KEY, name TEXT, rgb TEXT",
}
INDEXES = (
    "CREATE INDEX inventories_set_num ON inventories (set_num)",
    "CREATE INDEX inventory_parts_inventory_id ON inventory_parts (inventory_id)",
)


def load_table(connection, csv_dir, table, definition):
    columns = [column.split()[0] for column in definition.split(", ")]
    path = csv_dir / f"{table}.csv"
    with open(path, newline="", encoding="utf-8") as csv_file:
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


class Command(BaseCommand):
    help = "Builds the catalog database the site reads from the Rebrickable CSV files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-dir",
            type=Path,
            default=settings.CATALOG_CSV_DIR,
            help="Directory holding the extracted CSV files.",
        )

    def handle(self, *args, csv_dir, **options):
        database = Path(settings.CATALOG_DB)
        for table in TABLES:
            if not (csv_dir / f"{table}.csv").is_file():
                raise CommandError(f"Missing {table}.csv in {csv_dir}")

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
