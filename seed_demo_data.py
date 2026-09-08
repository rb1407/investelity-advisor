"""CLI entrypoint for seeding demo data locally.

Run: python scripts/seed_demo_data.py

Note: this now also runs automatically every time the app starts (see
core/app_common.py -> core/seed.py), so this script is only needed if you
want to seed the database without launching the app.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.seed import DEMO_PASSWORD, DEMO_USERNAME, seed


def main() -> None:
    seed(verbose=True)
    print("\nDone. Run: streamlit run Home.py")
    print(f"Log in with username='{DEMO_USERNAME}' password='{DEMO_PASSWORD}'")


if __name__ == "__main__":
    main()
