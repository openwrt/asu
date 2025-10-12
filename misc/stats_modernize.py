from asu.util import get_redis_ts

stat_types = (
    "cache-hits",
    "cache-misses",
    "failures",
    "requests",
    "successes",
)

ts = get_redis_ts()
rc = ts.client

converted = rc.exists("stats:build:requests")
force = False
if converted and not force:
    print("Already converted =====================")
else:
    print("Converting ============================")

    if rc.exists("stats:cache-misses"):
        # Note: "rename" overwrites any existing destination...
        rc.rename("stats:cache-misses", "stats:build:cache-misses")
    if rc.exists("stats:cache-hits"):
        # Old stats are completely incorrect, so just delete them.
        rc.delete("stats:cache-hits")

    for stat_type in stat_types:
        key = f"stats:build:{stat_type}"
        func = ts.alter if rc.exists(key) else ts.create
        func(key, labels={"stats": "summary"}, duplicate_policy="sum")

    # Attempt to repopulate total requests and success values as
    # accurately as possible using existing stats:builds:* data.
    ts.delete("stats:build:requests", "-", "+")  # Empty them out.
    ts.delete("stats:build:successes", "-", "+")
    all_builds = ts.mrange("-", "+", filters=["stats=builds"])
    for build in all_builds:
        _, data = build.popitem()
        series = data[1]
        for stamp, value in series:
            ts.add("stats:build:requests", timestamp=stamp, value=value)
            ts.add("stats:build:successes", timestamp=stamp, value=value)

    for stat_type in stat_types:
        key = f"stats:build:{stat_type}"
        print(f"{key:<25} - {ts.info(key).total_samples} samples")
