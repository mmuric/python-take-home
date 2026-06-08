# Question 2 — Decisions

## 1. What retry strategy did you implement and why? What alternatives did you consider?
I implemented exponential backoff with jitter: `delay = min(base × 2^(attempt-1) + random(0, base), max_backoff)`. Each subsequent retry waits longer, while a small random jitter prevents synchronized retry waves.

I considered two possible architectural alternatives: an in-memory queue (`queue.Queue`) versus an external message broker (`RabbitMQ`, `Redis Streams`). I picked `queue.Queue` because a broker would require additional infrastructure, which would be disproportionate for a tool of this scope.

The trade-off is that tasks queued at the moment of process termination are lost, whereas a real broker would persist them.

## 2. How did you implement timeout handling? What are the tradeoffs of your approach?
We used `ThreadPoolExecutor` with timeout resolution. However, a timeout here does not actually kill the task, since Python does not provide a safe `thread.kill()` mechanism. On timeout, we re-enqueue the task with backoff and submit a new future. The original thread continues running until natural completion. For idempotent tasks this is acceptable. However, for destructive tasks such as cleanup operations, the original thread and the retry thread may run concurrently, potentially producing race conditions.

## 3. What additional task type did you add and why? How does it demonstrate the framework's extensibility?
I implemented an additional `DataSyncTask`. This task type was missing from the original `executor.py`.

Extensibility is demonstrated structurally: the new class inherits from `Task`, implements `run()`, and the retry, timeout, queue, and summary mechanisms apply to it without any modification to `QueueExecutor`. The same machinery that runs `HealthCheckTask` also runs `DataSyncTask` uniformly. This includes timeout edge cases as well. `DataSyncTask("timeout")` sleeps longer than the configured timeout, triggers the timeout flow, and eventually results in `Status.TIMEOUT`.

## 4. Did you keep sequential execution or add concurrency? Why?
I added threading-based concurrency primitives (`ThreadPoolExecutor`) primarily for timeout enforcement and queue resilience, but the dispatch pattern remains sequential. So although a concurrency mechanism is in use, only one task runs at a time at the dispatch layer.

True parallel dispatch via `pool.map()` was considered but kept out of scope. Sequential execution is easier to understand, and the order of logs and retries is preserved. In the case of CPU-bound tasks, we could switch to `ProcessPoolExecutor` relatively easily.

## 5. What happens if a task fails all retry attempts? How is this surfaced to the operator?
When a task fails all retry attempts, we consider that task failed. The `run_all()` method returns a list of `TaskResult` objects with the following fields: status (`FAILED` | `TIMEOUT`), number of attempts, error (the last exception before failure), and `duration_seconds` (the duration of the last execution attempt).

Operators can filter and inspect `TaskResult` objects based on status.

All other tasks continue execution without interruption. Failures are isolated to the individual task.

Before the application exits, the operator can see a summary containing task statistics: total tasks, succeeded, failed, timed out, total attempts, total duration, and average duration per task.

Process exit code:
- `main()` returns `0` if all tasks succeeded.
- `main()` returns `1` otherwise.

At the moment, due to the minimal infrastructure used for this project, there is no dead-letter queue.

## 6. What did you skip or simplify? What would break in production?
Threads cannot be killed. On timeout, a new retry may run concurrently with the original task, which may still be executing. For idempotent tasks this is acceptable, but for destructive tasks it can cause race conditions.

We used an in-memory queue, so there is no persistence. If the process crashes or receives `SIGKILL`, all queued tasks are silently lost. A message broker with disk persistence would survive restarts and allow workers to replay pending tasks.

We do not have a dead-letter queue. Tasks that exhaust all retries appear in the summary during execution and then disappear when the process exits. For example, we cannot answer questions such as "What failed yesterday?"

There is no graceful shutdown mechanism. Process termination does not drain the queue before exiting. This means that in-flight tasks may be interrupted in the middle of execution, and the remaining queued tasks would be lost.