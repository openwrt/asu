from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily


class BuildCollector(object):
    def __init__(self, connection=None):
        self.connection = connection

    def collect(self):
        stats_builds = CounterMetricFamily(
            "builds",
            "Total number of built images",
            labels=["version", "target", "profile"],
        )
        for build, count in self.connection.hgetall("stats:builds").items():
            stats_builds.add_metric(build.decode().split("#"), count)

        yield stats_builds

        stats_clients = CounterMetricFamily(
            "clients",
            "Clients requesting images",
            labels=["name", "version"],
        )
        for client, count in self.connection.hgetall("stats:clients").items():
            stats_clients.add_metric(client.decode().split("/"), count)

        yield stats_clients

        hits = self.connection.get("stats:cache-hit")
        if hits:
            hits = int(hits.decode())
        else:
            hits = 0

        yield GaugeMetricFamily("cache_hits", "Cache hits of build images", value=hits)

        misses = self.connection.get("stats:cache-miss")

        if misses:
            misses = int(misses.decode())
        else:
            misses = 0

        yield GaugeMetricFamily(
            "cache_misses", "Cache misses of build images in percent", value=misses
        )
