from prometheus_client.core import CounterMetricFamily


class BuildCollector(object):
    def __init__(self, connection=None):
        self.connection = connection

    def collect(self):
        stats_builds = CounterMetricFamily(
            "builds",
            "Total number of built images",
            labels=["branch", "version", "target", "profile"],
        )
        for build, count in self.connection.hgetall("stats-builds").items():
            stats_builds.add_metric(build.decode().split("#"), count)

        yield stats_builds
