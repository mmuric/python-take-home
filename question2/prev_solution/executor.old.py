import logging
import sys
import time
from dataclasses import dataclass, field
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("executor")


class Status(Enum):
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class TaskResult:
    name: str
    status: Status
    duration_seconds: float
    error: str | None = None
    # TODO: attempts, timed_out


class Task:
    name = "base"

    def run(self):
        raise NotImplementedError


class HealthCheckTask(Task):
    name = "health_check"

    def __init__(self, endpoint):
        self.endpoint = endpoint

    def __str__(self):
        return f"{self.name}({self.endpoint})"

    def run(self):
        log.info("checking [%s]", self.endpoint)
        time.sleep(0.1)
        if self.endpoint == "fail":
            raise RuntimeError(f"health check failed for [{self.endpoint}]")
        log.info("[%s] healthy", self.endpoint)


class CleanupTask(Task):
    name = "cleanup"

    def __init__(self, target):
        self.target = target

    def __str__(self):
        return f"{self.name}({self.target})"

    def run(self):
        log.info("cleaning [%s]", self.target)
        time.sleep(0.05)
        if self.target == "fail":
            raise RuntimeError(f"cleanup failed for [{self.target}]")
        log.info("[%s] cleaned", self.target)


TASK_REGISTRY = {
    HealthCheckTask.name: HealthCheckTask,
    CleanupTask.name: CleanupTask,
}


@dataclass
class Executor:
    tasks: list = field(default_factory=list)
    # TODO: retry policy, timeout

    def add(self, task):
        self.tasks.append(task)

    def run_all(self):
        results = []
        for task in self.tasks:
            log.info("starting task: %s", task.name)
            results.append(self._run_one(task))
        self._print_summary(results)
        return results

    def _run_one(self, task):
        # TODO: retry + timeout
        start = time.monotonic()
        try:
            task.run()
            return TaskResult(task.name, Status.SUCCESS, time.monotonic() - start)
        except Exception as err:
            log.error("task %s failed: %s", task.name, err)
            return TaskResult(task.name, Status.FAILED, time.monotonic() - start, str(err))

    def _print_summary(self, results):
        total = len(results)
        ok = sum(1 for r in results if r.status == Status.SUCCESS)
        failed = sum(1 for r in results if r.status == Status.FAILED)
        log.info("summary: total=%d, succeeded=%d, failed=%d", total, ok, failed)
