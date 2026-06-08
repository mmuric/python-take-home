import sys

from .executor import CleanupTask, HealthCheckTask, Status
from .queue_executor import DataSyncTask, QueueExecutor


def main():
    executor = QueueExecutor()
    executor.add(HealthCheckTask("https://example.com"))
    executor.add(HealthCheckTask("fail"))
    executor.add(HealthCheckTask("https://example.com/api"))
    executor.add(CleanupTask("/home/user/www/tmp"))
    executor.add(DataSyncTask("source 1"))
    executor.add(DataSyncTask("source 1"))
    executor.add(DataSyncTask("timeout"))

    results = executor.run_all()
    return 0 if all(r.status == Status.SUCCESS for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
