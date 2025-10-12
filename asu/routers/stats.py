from datetime import datetime as dt, timedelta, UTC

from fastapi import APIRouter

from asu.util import get_redis_ts

router = APIRouter()


DAY_MS = 24 * 60 * 60 * 1000
N_DAYS = 30


@router.get("/builds-per-day")
def get_builds_per_day() -> dict:
    """
    References:
    https://redis.readthedocs.io/en/latest/redismodules.html#redis.commands.timeseries.commands.TimeSeriesCommands.range
    https://www.chartjs.org/docs/latest/charts/line.html
    """

    # "stop" is next midnight to define buckets on exact day boundaries.
    stop = dt.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    stop += timedelta(days=1)
    stop = int(stop.timestamp() * 1000)
    start = stop - N_DAYS * DAY_MS

    stamps = list(range(start, stop, DAY_MS))
    labels = [str(dt.fromtimestamp(stamp // 1000, UTC))[:10] + "Z" for stamp in stamps]

    ts = get_redis_ts()
    rc = ts.client
    range_options = dict(
        from_time=start,
        to_time=stop,
        align=start,  # Ensures alignment of X values with "stamps".
        aggregation_type="sum",
        bucket_size_msec=DAY_MS,
    )

    def get_dataset(event: str, color: str) -> dict:
        """Fills "data" array completely, supplying 0 for missing values."""
        key = f"stats:build:{event}"
        result = ts.range(key, **range_options) if rc.exists(key) else []
        data_map = dict(result)
        return {
            "label": event.title(),
            "data": [data_map.get(stamp, 0) for stamp in stamps],
            "color": color,
        }

    return {
        "labels": labels,
        "datasets": [
            # See add_build_event for valid "event" values.
            get_dataset("requests", "green"),
            get_dataset("cache-hits", "orange"),
            get_dataset("failures", "red"),
        ],
    }
