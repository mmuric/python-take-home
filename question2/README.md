# Question 2 — Extend the Task Executor

## Files

```
/
├── question2/
    ├── __main__.py           # entry point — composes tasks and runs QueueExecutor
    ├── executor.py           # baseline framework (Task, TaskResult, Executor, HealthCheckTask, CleanupTask)
    ├── queue_executor.py     # QueueExecutor (retry + timeout via Queue + ThreadPoolExecutor) + DataSyncTask
    └── tests/                # pytest tests for retry, timeout, mixed batches
```

# Setup

## Requirements

This project uses `uv` for dependency management and command execution.

Run `uv sync` from the project root (`/`). Make sure you execute the command from the root directory.

## Linting and Formatting

From the project root (`/`), run:
```
uv run ruff check question2
uv run ruff check question2 --fix
uv run ruff format question2
```

## Running the Task Executor

To run the task executor, execute the following command from the project root (`/`):

```
uv run python -m question2
```

This command will automatically execute several tasks from the queue and print a summary once execution is complete.

A few tasks are intentionally configured to fail, and some are expected to time out. This is done to demonstrate the retry, timeout, and error-handling mechanisms implemented in the framework.

## Tests

You can run the tests using the following command from the project root (`/`):

```
uv run pytest question2/tests -s -v 
```

