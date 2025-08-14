from datetime import datetime

from fastapi import APIRouter

from asu.util import get_redis_client

router = APIRouter()


def get_redis_ts():
    return get_redis_client().ts()


@router.get("/builds-per-day")
def get_builds_per_day():
    ts = get_redis_ts()
    now = int(datetime.utcnow().timestamp() * 1000)
    start = now - 30 * 24 * 60 * 60 * 1000  # last 30 days

    # aggregate all time series labeled with stats=builds
    results = ts.mrange(
        from_time=start,
        to_time=now,
        filters=["stats=builds"],
        with_labels=False,
        aggregation_type="sum",
        bucket_size_msec=86400000,  # 1 day (24 hours)
    )

    # create a map from timestamp to build count
    daily_counts = {}

    for entry in results:
        data = list(entry.values())[0][1]
        for ts, value in data:
            daily_counts[ts] = daily_counts.get(ts, 0) + int(value)

    # sort by timestamp
    sorted_data = sorted(daily_counts.items())

    labels = [datetime.utcfromtimestamp(ts / 1000).isoformat() for ts, _ in sorted_data]
    values = [count for _, count in sorted_data]

    return {
        "labels": labels,
        "datasets": [{"label": "Builds per day", "data": values}],
    }
