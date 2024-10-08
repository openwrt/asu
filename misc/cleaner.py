"""
Clean out the `public/store` directory, deleting all expired builds.

First, collect a set of all the hash keys from the current results.
Next, scan the `public/store` directories to see if they are in the set
(i.e., they are still being referenced in the database).  If not, then we
know the directory has expired, and we can delete it.

A host cron job to run this on a regular basis looks like this, where
`asu-venv` is your local Python virtual environment directory:

    cd ~/asu/ && . ~/asu-venv/bin/activate && python misc/cleaner.py
"""

from asu.util import get_redis_client
from asu.config import settings
from shutil import rmtree

HASH_LENGTH = 32  # Length of build hash, see util.py for details.

redis_client = get_redis_client()
active_hashes = {
    *filter(
        lambda h: len(h) == HASH_LENGTH,
        (key.split(":")[-1] for key in redis_client.keys("rq:*")),
    )
}

print(f"{active_hashes = }")

store = settings.public_path / "store"
for dir in store.glob("*"):
    # We check length as an added precaution against doing something stupid.
    if len(dir.name) == HASH_LENGTH and dir.name not in active_hashes:
        print(f"Delete it {dir = !s}")
        rmtree(dir)
    else:
        print(f"Keep it {dir = !s}")
