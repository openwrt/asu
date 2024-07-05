from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

from asu.util import get_redis_client

redis_client = get_redis_client()


class BuildCollector(object):
    def collect(self):
        stats_builds = CounterMetricFamily(
            "builds",
            "Total number of built images",
            labels=["version", "target", "profile"],
        )
        for build, count in redis_client.hgetall("stats:builds").items():
            stats_builds.add_metric(build.decode().split("#"), count)

        yield stats_builds

        stats_clients = CounterMetricFamily(
            "clients",
            "Clients requesting images",
            labels=["name", "version"],
        )
        for client, count in redis_client.hgetall("stats:clients").items():
            stats_clients.add_metric(client.decode().split("/"), count)

        yield stats_clients

        hits = redis_client.get("stats:cache-hit")
        if hits:
            hits = int(hits.decode())
        else:
            hits = 0

        yield GaugeMetricFamily("cache_hits", "Cache hits of build images", value=hits)

        misses = redis_client.get("stats:cache-miss")

        if misses:
            misses = int(misses.decode())
        else:
            misses = 0

        yield GaugeMetricFamily(
            "cache_misses", "Cache misses of build images in percent", value=misses
        )
