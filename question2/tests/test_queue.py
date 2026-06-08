from question2.queue_executor import DataSyncTask, QueueExecutor, Status


def _fast_executor(**overrides):
    return QueueExecutor(
        max_attempts=3,
        timeout_seconds=1,
        base_backoff=0.1,
        max_workers=2,
        max_backoff=0.2,
        **overrides,
    )


def test_retry_exhausted_returns_failed():
    executor = _fast_executor()
    task = DataSyncTask("fail")
    executor.add(task)
    result = executor.run_all()[0]
    assert result.status == Status.FAILED
    assert result.attempts == 3
    assert "data sync failed" in result.error.lower()


def test_timeout_returns_timeout():
    executor = _fast_executor()
    task = DataSyncTask("timeout")
    executor.add(task)
    result = executor.run_all()[0]
    assert result.status == Status.TIMEOUT
    assert result.attempts == 3


def test_successful_task():
    executor = _fast_executor()
    task = DataSyncTask("success")
    executor.add(task)
    result = executor.run_all()[0]
    assert result.status == Status.SUCCESS
    assert result.attempts == 1
