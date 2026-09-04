import argparse, os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent   # Repo-Root (tga_app/)


def load_dotenv(path):
    """Minimaler .env-Leser (KEY=VALUE), ohne Abhängigkeit."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main(argv=None):
    load_dotenv(ROOT / ".env")
    p = argparse.ArgumentParser(prog="tga_tools", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    k = sub.add_parser("katalog", help="Katalog-CSVs prüfen und nach Supabase schreiben")
    ks = k.add_subparsers(dest="kcmd", required=True)

    chk = ks.add_parser("check", help="nur lesen + validieren, nichts schreiben")
    chk.add_argument("--data", default=str(ROOT / "data"), help="Ordner mit den CSVs")

    imp = ks.add_parser("import", help="validieren und in kat_* schreiben (oder SQL-Datei erzeugen)")
    imp.add_argument("--data", default=str(ROOT / "data"))
    imp.add_argument("--dsn", default=os.environ.get("DATABASE_URL"),
                     help="Postgres-Verbindung (oder DATABASE_URL in .env). Supabase: Settings → Database → Connection string (URI)")
    imp.add_argument("--sql", metavar="DATEI", help="statt DB-Verbindung: Seed-SQL in diese Datei schreiben (für den SQL-Editor)")
    imp.add_argument("--version", help="Katalogversion für kat_meta (Default: heutiges Datum)")
    imp.add_argument("--force", action="store_true", help="auch bei Validierungsfehlern schreiben")
    imp.add_argument("--dry-run", action="store_true", help="alles außer dem Schreiben")

    a = p.parse_args(argv)
    if a.cmd == "katalog":
        from .katalog import cli
        return cli.run(a)


if __name__ == "__main__":
    sys.exit(main())
