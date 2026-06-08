import json
import sys

from .executor import TaskConfig
from .queue_executor import QueueExecutor

# DataSyncTask


def main():
    executor = QueueExecutor()

    test_configs = [
        TaskConfig(
            task_id="check-google",
            task_type="http_check",
            target="https://www.google.com",
            params={"expected_status": 200},
        ),
        TaskConfig(
            task_id="check-fake",
            task_type="http_check",
            target="https://this-does-not-exist.invalid",
            params={"expected_status": 200},
        ),
        TaskConfig(
            task_id="slow-job",
            task_type="subprocess",
            target="sleep",
            params={"args": ["30"]},
            timeout_seconds=2,  # garantovan timeout posle 2s
            max_attempts=2,
        ),
    ]

    executor.run_all(test_configs)
    print(json.dumps(executor.summary(), indent=2))


if __name__ == "__main__":
    sys.exit(main())
