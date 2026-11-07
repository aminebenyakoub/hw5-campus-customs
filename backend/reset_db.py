"""Reset the working database: copy data/campus_customs.db over data/campus_customs_new.db.

The original file is only read. The audit trail is NOT touched (it is append-only).
"""

import shutil

from config import ORIGINAL_DB, WORKING_DB


def reset_working_db() -> None:
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)


if __name__ == "__main__":
    reset_working_db()
    print(f"Reset {WORKING_DB.name} from {ORIGINAL_DB.name}")
