import random
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from enum import Enum
from queue import Queue

from .executor import Executor, Task, log


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
    attempts: int = 1


class DataSyncTask(Task):
    name = "data_sync"

    def __init__(self, source):
        self.source = source

    def __str__(self):
        return f"{self.name}({self.source})"

    def run(self):
        log.info("syncing [%s] started", self.source)
        time.sleep(0.1)
        if self.source == "fail":
            raise RuntimeError(f"data sync failed for [{self.source}]")
        if self.source == "timeout":
            time.sleep(5)
        log.info("syncing [%s] completed", self.source)


class QueueExecutor(Executor):
    def __init__(
        self, max_attempts=3, timeout_seconds=1, base_backoff=0.5, max_workers=2, max_backoff=2
    ):
        super().__init__()
        self.max_attempts = max_attempts
        self.timeout_seconds = timeout_seconds
        self.base_backoff = base_backoff
        self.max_workers = max_workers
        self.max_backoff = max_backoff

    def _delay_for_attempt(self, attempt):
        delay = self.base_backoff * (2 ** (attempt - 1)) + random.uniform(0, self.base_backoff)
        return min(delay, self.max_backoff)

    def _print_summary(self, results):
        total = len(results)

        ok = sum(1 for r in results if r.status == Status.SUCCESS)
        failed = sum(1 for r in results if r.status == Status.FAILED)
        timeout = sum(1 for r in results if r.status == Status.TIMEOUT)

        total_attempts = sum(r.attempts for r in results)
        retried = sum(1 for r in results if r.attempts > 1)
        total_duration = sum(r.duration_seconds for r in results)
        avg_duration = total_duration / total if total else 0.0

        log.info(
            "\n\nSUMMARY: total=%d succeeded=%d failed=%d timeout=%d "
            "| attempts=%d retried=%d | duration=%.2fs (avg %.2fs/task)\n",
            total,
            ok,
            failed,
            timeout,
            total_attempts,
            retried,
            total_duration,
            avg_duration,
        )

    def run_all(self):
        results = []
        q = Queue()
        for task in self.tasks:
            q.put((task, 1))
        pool = ThreadPoolExecutor(max_workers=self.max_workers)
        try:
            while not q.empty():
                task, attempt = q.get()
                result = self._run_one(task, attempt, pool, q)
                if result is not None:
                    results.append(result)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        self._print_summary(results)
        return results

    def _run_one(self, task, attempt, pool, q):
        prefix = f"[{task.name} attempt={attempt}]"
        log.info("%s starting", prefix)
        future = pool.submit(task.run)
        start = time.monotonic()
        try:
            future.result(timeout=self.timeout_seconds)
            duration = time.monotonic() - start
            return TaskResult(
                task.name, Status.SUCCESS, duration_seconds=duration, attempts=attempt
            )
        except FuturesTimeoutError:
            log.warning("%s timed out after %.1fs", prefix, self.timeout_seconds)

            if attempt < self.max_attempts:
                delay = self._delay_for_attempt(attempt)
                time.sleep(delay)
                q.put((task, attempt + 1))
                return None
            else:
                duration = time.monotonic() - start
                return TaskResult(
                    task.name, Status.TIMEOUT, duration_seconds=duration, attempts=attempt
                )

        except Exception as err:
            log.error("%s failed: %s", prefix, err)

            if attempt < self.max_attempts:
                delay = self._delay_for_attempt(attempt)
                time.sleep(delay)
                q.put((task, attempt + 1))
                return None
            else:
                duration = time.monotonic() - start
                return TaskResult(
                    task.name,
                    Status.FAILED,
                    duration_seconds=duration,
                    error=str(err),
                    attempts=attempt,
                )
