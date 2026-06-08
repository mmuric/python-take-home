from question2.executor import TaskConfig, TaskStatus
from question2.queue_executor import QueueExecutor


def _config(task_id, task_type, target, **kwargs):
    return TaskConfig(
        task_id=task_id,
        task_type=task_type,
        target=target,
        max_attempts=kwargs.get("max_attempts", 3),
        timeout_seconds=kwargs.get("timeout_seconds", 0.5),
        base_backoff=kwargs.get("base_backoff", 0.01),
        max_backoff=kwargs.get("max_backoff", 0.05),
        params=kwargs.get("params", {}),
    )


def test_retry_exhausted_returns_failed():
    executor = QueueExecutor()
    configs = [_config("fail-job", "subprocess", "false")]
    results = executor.run_all(configs)
    assert results[0].status == TaskStatus.FAILED
    assert results[0].attempts == 3


def test_timeout_returns_timeout():
    executor = QueueExecutor()
    configs = [_config(
        "slow-job", "subprocess", "sleep",
        params={"args": ["10"]},
        timeout_seconds=0.1,
        max_attempts=2,
    )]
    results = executor.run_all(configs)
    assert results[0].status == TaskStatus.TIMEOUT
    assert results[0].attempts == 2

def test_successful_task():
    executor = QueueExecutor()
    configs = [_config(
        "echo-job", "subprocess", "echo",
        params={"args": ["hello"]},
    )]
    results = executor.run_all(configs)
    assert results[0].status == TaskStatus.SUCCESS
    assert results[0].attempts == 1
    assert results[0].result_data["returncode"] == 0
    assert "hello" in results[0].result_data["stdout"]
