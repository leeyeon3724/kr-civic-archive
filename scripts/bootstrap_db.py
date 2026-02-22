import subprocess
import sys


def main() -> None:
    cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]
    subprocess.run(cmd, check=True)
    print("Database migration to head completed.")


if __name__ == "__main__":
    main()
