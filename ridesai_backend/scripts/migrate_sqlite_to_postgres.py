#!/usr/bin/env python
"""
Zero-Data-Loss Migration Script: SQLite (db.sqlite3) -> PostgreSQL

Executes a safe, 6-step migration pipeline:
  1. Timestamped backup of db.sqlite3 (stored in ridesai_backend/backups/)
  2. Clean UTF-8 fixture export from SQLite via Django dumpdata
     (--natural-foreign --natural-primary, excluding contenttypes,
      auth.permission, admin.logentry, sessions.session)
  3. PostgreSQL connection verification & schema creation (manage.py migrate)
  4. UTF-8 fixture import into PostgreSQL (manage.py loaddata)
  5. PostgreSQL sequence reset (manage.py sqlsequencereset) across all apps
  6. Row-count integrity verification comparing SQLite vs. PostgreSQL

Usage:
    python scripts/migrate_sqlite_to_postgres.py
    python scripts/migrate_sqlite_to_postgres.py --dry-run
"""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
MANAGE_PY = BACKEND_DIR / "manage.py"
SQLITE_PATH = BACKEND_DIR / "db.sqlite3"
BACKUP_DIR = BACKEND_DIR / "backups"

EXCLUDED_APPS = [
    "contenttypes",
    "auth.permission",
    "admin.logentry",
    "sessions.session",
]

PROJECT_APPS = [
    "accounts",
    "billing",
    "companies",
    "operations",
    "employee",
]


def _make_env(use_sqlite: bool) -> dict:
    env = os.environ.copy()
    env["USE_SQLITE"] = "True" if use_sqlite else "False"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run_manage(args: list[str], use_sqlite: bool, capture_output: bool = False) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-X", "utf8", str(MANAGE_PY), *args]
    result = subprocess.run(
        cmd,
        cwd=str(BACKEND_DIR),
        env=_make_env(use_sqlite=use_sqlite),
        capture_output=capture_output,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        if capture_output:
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"Command failed (exit {result.returncode}): {' '.join(cmd)}")
    return result


def step_1_backup_sqlite(timestamp: str) -> Path:
    print("\n[Step 1/6] Creating timestamped backup of db.sqlite3...")
    if not SQLITE_PATH.exists():
        raise FileNotFoundError(f"SQLite database not found at {SQLITE_PATH}")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"db.sqlite3.backup.{timestamp}"
    shutil.copy2(SQLITE_PATH, backup_path)
    size_kb = backup_path.stat().st_size / 1024.0
    print(f"  OK: Backup saved to {backup_path} ({size_kb:.1f} KB)")
    return backup_path


def step_2_export_fixture(timestamp: str) -> Path:
    print("\n[Step 2/6] Exporting SQLite data via dumpdata (UTF-8, natural keys)...")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    fixture_path = BACKUP_DIR / f"sqlite_export_{timestamp}.json"

    args = [
        "dumpdata",
        "--natural-foreign",
        "--natural-primary",
        "--indent", "2",
        "-o", str(fixture_path),
    ]
    for excluded in EXCLUDED_APPS:
        args.extend(["--exclude", excluded])

    _run_manage(args, use_sqlite=True)

    with open(fixture_path, "r", encoding="utf-8") as fh:
        records = json.load(fh)
    print(f"  OK: Exported {len(records)} records to {fixture_path}")
    return fixture_path


def step_3_verify_and_migrate_postgres(dry_run: bool = False) -> dict:
    print("\n[Step 3/6] Verifying PostgreSQL connection and applying migrations...")
    check_code = (
        "import json, django; "
        "from django.db import connection; "
        "connection.ensure_connection(); "
        "info = {'engine': connection.settings_dict.get('ENGINE'), "
        "'name': connection.settings_dict.get('NAME'), "
        "'host': connection.settings_dict.get('HOST'), "
        "'port': connection.settings_dict.get('PORT')}; "
        "print(json.dumps(info))"
    )
    res = subprocess.run(
        [sys.executable, "-X", "utf8", str(MANAGE_PY), "shell", "-c", check_code],
        cwd=str(BACKEND_DIR),
        env=_make_env(use_sqlite=False),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        raise RuntimeError(
            "Could not connect to PostgreSQL. Verify DATABASE_URL or DB_* variables in ridesai_backend/.env "
            "and ensure the PostgreSQL service is running."
        )

    info_line = [line for line in res.stdout.strip().splitlines() if line.strip().startswith("{")][-1]
    info = json.loads(info_line)
    if "postgresql" not in str(info.get("engine", "")):
        raise RuntimeError(
            f"Target engine is '{info.get('engine')}', not PostgreSQL! "
            "Set DATABASE_URL or DB_NAME in ridesai_backend/.env before running this migration."
        )
    print(f"  OK: Connected to PostgreSQL database '{info['name']}' at {info['host']}:{info['port']}")

    if dry_run:
        print("  [DRY-RUN] Skipping `manage.py migrate` execution.")
        return info

    _run_manage(["migrate", "--noinput"], use_sqlite=False)
    print("  OK: All Django migrations applied cleanly to PostgreSQL.")
    return info


def _clear_seeded_rows_if_fresh_db(fixture_path: Path) -> None:
    """
    If PostgreSQL has 0 users and 0 companies (freshly migrated DB), remove any
    migration-seeded rows (e.g. companies.Plan from 0006_seed_default_polar_plan)
    when the SQLite fixture already includes records for those models, preventing
    unique-constraint or PK conflicts during loaddata.
    """
    with open(fixture_path, "r", encoding="utf-8") as fh:
        records = json.load(fh)
    fixture_models = {r.get("model") for r in records}

    prep_code = f"""
from accounts.models import User
from companies.models import Company, Plan
if User.objects.count() == 0 and Company.objects.count() == 0:
    fixture_models = {sorted(fixture_models)!r}
    if "companies.plan" in fixture_models:
        deleted, _ = Plan.objects.all().delete()
        if deleted:
            print(f"  Cleared {{deleted}} migration-seeded Plan row(s) prior to loaddata.")
"""
    _run_manage(["shell", "-c", prep_code], use_sqlite=False)


def step_4_load_fixture(fixture_path: Path, dry_run: bool = False) -> None:
    print("\n[Step 4/6] Loading UTF-8 fixture into PostgreSQL...")
    if dry_run:
        print(f"  [DRY-RUN] Skipping `manage.py loaddata {fixture_path}`.")
        return

    _clear_seeded_rows_if_fresh_db(fixture_path)
    _run_manage(["loaddata", str(fixture_path)], use_sqlite=False)
    print("  OK: Fixture loaded into PostgreSQL without errors.")


def step_5_reset_sequences(dry_run: bool = False) -> None:
    print("\n[Step 5/6] Resetting PostgreSQL auto-increment sequences...")
    if dry_run:
        print("  [DRY-RUN] Skipping `sqlsequencereset` execution.")
        return

    reset_code = """
import io
from django.apps import apps
from django.core.management import call_command
from django.db import connection, transaction

app_labels = [app.label for app in apps.get_app_configs() if list(app.get_models())]
buf = io.StringIO()
call_command("sqlsequencereset", *app_labels, stdout=buf, no_color=True)
sql = buf.getvalue().strip()
statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("--")]
with transaction.atomic():
    with connection.cursor() as cursor:
        for stmt in statements:
            cursor.execute(stmt)
print(f"  OK: Reset {len(statements)} PostgreSQL sequence(s) across {len(app_labels)} app(s).")
"""
    _run_manage(["shell", "-c", reset_code], use_sqlite=False)


def _fetch_model_counts(use_sqlite: bool) -> dict[str, int]:
    count_code = f"""
import json
from django.apps import apps
counts = {{}}
for app_label in {PROJECT_APPS!r}:
    try:
        app_cfg = apps.get_app_config(app_label)
    except LookupError:
        continue
    for model in app_cfg.get_models():
        key = f"{{app_label}}.{{model.__name__}}"
        counts[key] = model.objects.count()
print("COUNTS_JSON:" + json.dumps(counts, sort_keys=True))
"""
    res = _run_manage(["shell", "-c", count_code], use_sqlite=use_sqlite, capture_output=True)
    for line in reversed(res.stdout.splitlines()):
        if line.startswith("COUNTS_JSON:"):
            return json.loads(line[len("COUNTS_JSON:"):])
    raise RuntimeError("Failed to read model counts from Django shell.")


def step_6_verify_integrity(dry_run: bool = False) -> bool:
    print("\n[Step 6/6] Verifying row counts (SQLite vs. PostgreSQL)...")
    if dry_run:
        print("  [DRY-RUN] Skipping live row-count comparison.")
        return True

    sqlite_counts = _fetch_model_counts(use_sqlite=True)
    pg_counts = _fetch_model_counts(use_sqlite=False)

    all_models = sorted(set(sqlite_counts.keys()) | set(pg_counts.keys()))
    mismatches = []

    header = f"  {'Model':<42} | {'SQLite':>8} | {'Postgres':>8} | Status"
    print(header)
    print("  " + "-" * (len(header) - 2))

    total_sqlite = 0
    total_pg = 0
    for model_name in all_models:
        s_cnt = sqlite_counts.get(model_name, 0)
        p_cnt = pg_counts.get(model_name, 0)
        total_sqlite += s_cnt
        total_pg += p_cnt
        ok = s_cnt == p_cnt
        if not ok:
            mismatches.append((model_name, s_cnt, p_cnt))
        if s_cnt > 0 or p_cnt > 0 or not ok:
            status = "MATCH" if ok else "MISMATCH"
            print(f"  {model_name:<42} | {s_cnt:>8} | {p_cnt:>8} | {status}")

    print("  " + "-" * (len(header) - 2))
    print(f"  {'TOTAL (all project models)':<42} | {total_sqlite:>8} | {total_pg:>8} | {'OK' if not mismatches else 'FAILED'}")

    if mismatches:
        print(f"\nERROR: {len(mismatches)} model(s) had row count mismatches!", file=sys.stderr)
        return False

    print(f"\nSUCCESS: 100% row-count parity verified across {len(all_models)} models ({total_pg} total rows migrated).")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate RidesAI database from SQLite to PostgreSQL with zero data loss.")
    parser.add_argument("--dry-run", action="store_true", help="Backup SQLite, export fixture, and verify PG connection without modifying PostgreSQL.")
    parser.add_argument("--skip-backup", action="store_true", help="Skip creating a db.sqlite3 backup copy.")
    args = parser.parse_args()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    print("=" * 72)
    print("RidesAI Zero-Data-Loss Migration: SQLite -> PostgreSQL")
    print("=" * 72)

    if not args.skip_backup:
        step_1_backup_sqlite(timestamp)
    else:
        print("\n[Step 1/6] Skipped backup (--skip-backup).")

    fixture_path = step_2_export_fixture(timestamp)
    step_3_verify_and_migrate_postgres(dry_run=args.dry_run)
    step_4_load_fixture(fixture_path, dry_run=args.dry_run)
    step_5_reset_sequences(dry_run=args.dry_run)
    ok = step_6_verify_integrity(dry_run=args.dry_run)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
