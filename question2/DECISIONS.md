> ⚠️ SECURITY: executes arbitrary commands as the calling user.
> Review TaskConfig before running — target='rm', args=['-rf', '/'] WILL execute destructively.
> No shell parsing, but named command runs directly.
> Production: add binary allowlist via validate().

# Question 2 — Decisions

## 1. What retry strategy did you implement and why? What alternatives did you consider?
I implemented exponential backoff with jitter: `delay = min(base × 2^(attempt-1) + random(0, base), max_backoff)`. Each subsequent retry waits longer, while a small random jitter prevents synchronized retry waves.

I considered two possible architectural alternatives: an in-memory queue (`queue.Queue`) versus an external message broker (`RabbitMQ`, `Redis Streams`). I picked `queue.Queue` because a broker would require additional infrastructure, which would be disproportionate for a tool of this scope.

The trade-off is that tasks queued at the moment of process termination are lost, whereas a real broker would persist them.

`TaskConfig` was extended in place (per spec's EXTEND THIS marker and TODO comments) rather than subclassed, adding max_attempts, timeout_seconds, base_backoff, and max_backoff directly on the existing dataclass. Subclassing was considered but rejected because spec explicitly invites in-place extension.

## 2. How did you implement timeout handling? What are the tradeoffs of your approach?
We used `ThreadPoolExecutor` with timeout resolution. However, a timeout here does not actually kill the task, since Python does not provide a safe `thread.kill()` mechanism. On timeout, we re-enqueue the task with backoff and submit a new future. The original thread continues running until natural completion. For idempotent tasks this is acceptable. However, for destructive tasks such as cleanup operations, the original thread and the retry thread may run concurrently, potentially producing race conditions.

## 3. What additional task type did you add and why? How does it demonstrate the framework's extensibility?
I implemented `SubprocessTask`. A new class is registered as `subprocess`, used for common ops patterns (cleanup scripts, rsync, pg_dump, log rotation). This task executes a shell command via `subprocess

**See SECURITY notice at the top of this file — `SubprocessTask` executes arbitrary commands as the calling user; review every `TaskConfig` before invocation.**

Extensibility is demonstrated structurally: `SubprocessTask` subclasses `BaseTask`, implements `execute()` (returning a result dict), and registers itself via the `@register_task("subprocess")` decorator. The retry, timeout, queue dispatch, and summary mechanisms in `QueueExecutor` apply uniformly without any modification. The same machinery that runs `HttpCheckTask` runs `SubprocessTask`, including the timeout edge case (`target="sleep"`, `args=["30"]`, `timeout_seconds=1` triggers the timeout flow and eventually surfaces as `TaskStatus.TIMEOUT`).

## 4. Did you keep sequential execution or add concurrency? Why?
I added threading-based concurrency primitives (`ThreadPoolExecutor`) primarily for timeout enforcement and queue resilience, but the dispatch pattern remains sequential. So although a concurrency mechanism is in use, only one task runs at a time at the dispatch layer.

QueueExecutor.run_task overrides the parent TaskExecutor.run_task(self, config) signature, accepting additional attempt, pool, and q parameters. The override is intentional: had we instead introduced a separate _run_one(self, config, attempt, pool, q) method, the parent's run_task(self, config) would remain callable and a caller might accidentally invoke it, bypassing retry, timeout, and queue logic entirely, producing inconsistent results. By shadowing the parent method with the retry-aware version, every call path is forced through the retry-aware implementation.

## 5. What happens if a task fails all retry attempts? How is this surfaced to the operator?
When a task fails all retry attempts, we consider that task failed. The `run_all()` method returns a list of `TaskResult` objects with the following fields: status (FAILED | TIMEOUT for retry-exhausted tasks), attempts (how many were spent), error_message (string representation of the last exception), and started_at / completed_at timestamps (operators compute duration as the delta if needed).

Operators can filter and inspect `TaskResult` objects based on status.

All other tasks continue execution without interruption. Failures are isolated to the individual task.

Before the application exits, the operator can call `summary` for a summary containing task statistics: total tasks, succeeded, failed, timed out, total attempts, and retried (count of tasks that required more than one attempt).

At the moment, due to the minimal infrastructure used for this project, there is no dead-letter queue.

## 6. What did you skip or simplify? What would break in production?
Threads cannot be killed — and for `SubprocessTask` the problem is doubled: even when the future raises `TimeoutError`, the original subprocess (`/bin/sleep`, `rsync`, a cleanup script, whatever the operator wired in) keeps running in its own OS process. The retry then submits a new future, spawns a new subprocess, and you end up with two parallel instances of the same operation. For a cleanup script that deletes files, this means double-delete races on the same path. Production hardening would use `subprocess.Popen` + `terminate()` / `kill()` on timeout, or wrap the task in `multiprocessing` for real cancellation. For idempotent tasks (HTTP health checks) the concurrent execution is acceptable.

`SubprocessTask` exposes arbitrary command execution under the calling process user. Production would require either a binary allowlist enforced in `validate()`, or a constrained UID via `subprocess.Popen(user=...)`. As shipped, an operator with write access to `TaskConfig` payloads can run any command (`rm -rf`, network exfiltration scripts, anything in `$PATH`). The framework relies entirely on operator review before invocation — see the SECURITY notice at the top of this file.

We used an in-memory queue, so there is no persistence. If the process crashes or receives `SIGKILL`, all queued tasks are silently lost. A message broker with disk persistence would survive restarts and allow workers to replay pending tasks.

We do not have a dead-letter queue. Tasks that exhaust all retries appear in the summary during execution and then disappear when the process exits. For example, we cannot answer questions such as "What failed yesterday?"

There is no graceful shutdown mechanism. Process termination does not drain the queue before exiting. This means that in-flight tasks may be interrupted in the middle of execution, and the remaining queued tasks would be lost.