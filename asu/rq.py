from re import compile
from pathlib import Path
from rq import Queue, Worker
from rq.job import Job
from podman import PodmanClient
from shutil import rmtree

from asu.config import settings
from asu.util import log, get_podman

REQUEST_HASH_LENGTH = 64
store: Path = settings.public_path / "store"
podman: PodmanClient = get_podman()


class GCWorker(Worker):
    """A Worker class that does periodic garbage collection on ASU's
    public store directory.  We tie into the standard `Worker` maintenance
    sequence, so the period is controlled by the base class.  You may change
    the garbage collection frequency in podman-compose.yml by adding a
    `--maintenance-interval` option to the startup command as follows (the
    default is 600 seconds).

    >>> command: rqworker ... --maintenance-interval 1800
    """

    hash_match = compile(f"^[0-9a-f]{{{REQUEST_HASH_LENGTH}}}$")

    def clean_store(self) -> None:
        """For performance testing, the store directory was mounted on a
        slow external USB hard drive.  A typical timing result showed ~1000
        directories deleted per second on that test system.  The synthetic
        test directories were created containing 10 files in each.
        File count dominated the timing, with file size being relatively
        insignificant, likely due to `stat` calls being the bottleneck.
        (Just for comparison, tests against store mounted on a fast SSD
        were about twice as fast.)

        >>> Cleaning /mnt/slow/public/store: deleted 5000/5000 builds
        >>> Timing analysis for clean_store: 5.081s
        """

        deleted: int = 0
        total: int = 0
        dir: Path
        queue: Queue
        for dir in store.glob("*"):
            if not dir.is_dir() or not self.hash_match.match(dir.name):
                continue
            total += 1
            for queue in self.queues:
                job: Job = queue.fetch_job(dir.name)
                log.info(f"  Found {dir.name = } {job = }")
                if job is None:
                    rmtree(dir)
                    deleted += 1

        log.info(f"Cleaning {store}: deleted {deleted}/{total} builds")

    def clean_podman(self) -> None:
        """Reclaim space from the various podman disk entities as they are orphaned."""
        removed = podman.containers.prune()
        log.info(f"Reclaimed {removed.get('SpaceReclaimed', 0):,d}B from containers")
        removed = podman.images.prune()
        log.info(f"Reclaimed {removed.get('SpaceReclaimed', 0):,d}B from images")
        removed = podman.volumes.prune()
        log.info(f"Reclaimed {removed.get('SpaceReclaimed', 0):,d}B from volumes")

    def run_maintenance_tasks(self):
        super().run_maintenance_tasks()
        self.clean_store()
        self.clean_podman()
