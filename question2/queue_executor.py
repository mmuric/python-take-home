import logging
import random
import time
import subprocess
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import UTC, datetime
from queue import Queue
from typing import Any

from .executor import (
    BaseTask,
    TaskConfig,
    TaskExecutor,
    TaskResult,
    TaskStatus,
    get_task_class,
    register_task,
)


class QueueExecutor(TaskExecutor):
    def __init__(self, logger: logging.Logger | None = None, max_workers: int = 2):
        super().__init__(logger)
        self.max_workers = max_workers

    def run_all(self, configs: list[TaskConfig]) -> list[TaskResult]:
        self.results = []
        q = Queue()
        for task_cfg in configs:
            q.put((task_cfg, 1))
        pool = ThreadPoolExecutor(max_workers=self.max_workers)
        try:
            while not q.empty():
                task_cfg, attempt = q.get()
                result = self.run_task(task_cfg, attempt, pool, q)
                if result is not None:
                    self.results.append(result)
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

        return self.results

    def run_task(
        self, config: TaskConfig, attempt: int, pool: ThreadPoolExecutor, q: Queue
    ) -> TaskResult:
        task_class = get_task_class(config.task_type)
        task = task_class(config, self.logger)

        if not task.validate():
            return TaskResult(
                task_id=config.task_id,
                status=TaskStatus.FAILED,
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                error_message=f"validation failed: {config.task_id}",
                attempts=attempt,
            )

        future = pool.submit(task.execute)
        started_at = datetime.now(UTC)
        try:
            result_data = future.result(timeout=config.timeout_seconds)

            return TaskResult(
                task_id=config.task_id,
                status=TaskStatus.SUCCESS,
                started_at=started_at,
                completed_at=datetime.now(UTC),
                result_data=result_data,
                attempts=attempt,
            )

        except FuturesTimeoutError:
            self.logger.warning(
                "timed out after %.1fs (attempt=%d)", config.timeout_seconds, attempt
            )

            if attempt < config.max_attempts:
                delay = self._delay_for_attempt(config, attempt)
                time.sleep(delay)
                q.put((config, attempt + 1))
                return None
            else:
                return TaskResult(
                    task_id=config.task_id,
                    status=TaskStatus.TIMEOUT,
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                    attempts=attempt,
                )

        except Exception as err:
            self.logger.error("failed: %s (attempt=%d)", err, attempt)

            if attempt < config.max_attempts:
                delay = self._delay_for_attempt(config, attempt)
                time.sleep(delay)
                q.put((config, attempt + 1))
                return None
            else:
                return TaskResult(
                    task_id=config.task_id,
                    status=TaskStatus.FAILED,
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                    attempts=attempt,
                    error_message=str(err),
                )

    def _delay_for_attempt(self, config: TaskConfig, attempt: int) -> float:
        delay = config.base_backoff * (2 ** (attempt - 1)) + random.uniform(0, config.base_backoff)
        return min(delay, config.max_backoff)

    def summary(self) -> dict[str, Any]:
        base = super().summary()
        base["timeout"] = sum(1 for r in self.results if r.status == TaskStatus.TIMEOUT)
        base["total_attempts"] = sum(r.attempts for r in self.results)
        base["retried"] = sum(1 for r in self.results if r.attempts > 1)
        return base


@register_task("subprocess")
class SubprocessTask(BaseTask):
    # Runs a shell command. Common ops pattern (cleanup scripts, rsync, etc)

    def execute(self) -> dict[str, Any]:
        args = [self.config.target, *self.config.params.get("args", [])]
        self.logger.info(f"Running: {' '.join(args)}")

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"exit {e.returncode}: {e.stderr.strip()[:200]}") from e

        return {
            "command": args,
            "stdout": result.stdout[:500],  # truncate to avoid log bloat
            "returncode": result.returncode,
        }
