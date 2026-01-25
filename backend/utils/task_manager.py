"""
Background Task Manager for QUANT INDUSTRY
===========================================
Provides a centralized manager for background tasks with:
- Task scheduling and execution
- Cancellation support
- Progress tracking
- Error handling
- Resource cleanup

Matches quant-platform pattern for async task management.
"""

import asyncio
import logging
import threading
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, Union

logger = logging.getLogger(__name__)


# ============== TASK TYPES ==============

class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class TaskPriority(Enum):
    """Task execution priority"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class TaskResult:
    """Result of a task execution"""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: float = 0.0

    @property
    def is_success(self) -> bool:
        return self.status == TaskStatus.COMPLETED

    @property
    def is_done(self) -> bool:
        return self.status in (
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.TIMEOUT
        )


@dataclass
class TaskInfo:
    """Information about a task"""
    id: str
    name: str
    status: TaskStatus
    priority: TaskPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: float = 0.0
    progress_message: str = ""
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    can_cancel: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "priority": self.priority.value,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "progress": self.progress,
            "progress_message": self.progress_message,
            "error": self.error,
            "metadata": self.metadata,
            "can_cancel": self.can_cancel
        }


# ============== TASK BASE CLASS ==============

class Task(ABC):
    """
    Abstract base class for background tasks.

    Example:
        class DataSyncTask(Task):
            async def execute(self, context: TaskContext) -> Any:
                for i, item in enumerate(items):
                    if context.is_cancelled:
                        return None
                    await self.process_item(item)
                    context.update_progress(i / len(items), f"Processing {item}")
                return {"processed": len(items)}
    """

    def __init__(
        self,
        name: str = None,
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: float = None,
        can_cancel: bool = True
    ):
        self.name = name or self.__class__.__name__
        self.priority = priority
        self.timeout = timeout
        self.can_cancel = can_cancel

    @abstractmethod
    async def execute(self, context: 'TaskContext') -> Any:
        """Execute the task"""
        pass

    async def on_cancel(self) -> None:
        """Called when task is cancelled"""
        pass

    async def on_error(self, error: Exception) -> None:
        """Called when task fails"""
        pass

    async def cleanup(self) -> None:
        """Called after task completes (success, failure, or cancel)"""
        pass


class TaskContext:
    """
    Context passed to task execution.
    Provides cancellation checking and progress reporting.
    """

    def __init__(self, task_id: str, manager: 'TaskManager'):
        self.task_id = task_id
        self._manager = manager
        self._cancelled = asyncio.Event()
        self._progress = 0.0
        self._progress_message = ""

    @property
    def is_cancelled(self) -> bool:
        """Check if task cancellation was requested"""
        return self._cancelled.is_set()

    def check_cancelled(self) -> None:
        """Raise CancelledError if cancelled"""
        if self.is_cancelled:
            raise asyncio.CancelledError("Task was cancelled")

    def update_progress(
        self,
        progress: float,
        message: str = ""
    ) -> None:
        """Update task progress"""
        self._progress = min(1.0, max(0.0, progress))
        self._progress_message = message
        self._manager._update_task_progress(
            self.task_id,
            self._progress,
            message
        )

    def _request_cancel(self) -> None:
        """Request task cancellation"""
        self._cancelled.set()


# ============== TASK MANAGER ==============

class TaskManager:
    """
    Centralized manager for background tasks.

    Features:
    - Async task execution with cancellation
    - Priority-based scheduling
    - Concurrent execution limits
    - Progress tracking
    - Error handling

    Example:
        manager = TaskManager(max_concurrent=5)
        await manager.start()

        # Submit a task
        task_id = await manager.submit(MyTask())

        # Check status
        info = manager.get_task_info(task_id)

        # Cancel if needed
        await manager.cancel(task_id)

        # Wait for result
        result = await manager.wait_for(task_id)

        await manager.stop()
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        default_timeout: float = 300.0
    ):
        """
        Initialize task manager.

        Args:
            max_concurrent: Maximum concurrent tasks
            default_timeout: Default task timeout in seconds
        """
        self.max_concurrent = max_concurrent
        self.default_timeout = default_timeout

        self._tasks: Dict[str, TaskInfo] = {}
        self._contexts: Dict[str, TaskContext] = {}
        self._futures: Dict[str, asyncio.Future] = {}
        self._pending: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running: Set[str] = set()

        self._started = False
        self._stopping = False
        self._worker_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the task manager"""
        if self._started:
            return

        self._started = True
        self._stopping = False
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("TaskManager started")

    async def stop(self, wait: bool = True, timeout: float = 30.0) -> None:
        """
        Stop the task manager.

        Args:
            wait: Wait for running tasks to complete
            timeout: Maximum wait time
        """
        self._stopping = True

        if wait and self._running:
            try:
                await asyncio.wait_for(
                    self._wait_all_complete(),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for tasks, cancelling remaining")
                await self.cancel_all()

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        self._started = False
        logger.info("TaskManager stopped")

    async def _wait_all_complete(self) -> None:
        """Wait for all running tasks to complete"""
        while self._running:
            await asyncio.sleep(0.1)

    async def submit(
        self,
        task: Task,
        task_id: str = None
    ) -> str:
        """
        Submit a task for execution.

        Args:
            task: Task to execute
            task_id: Optional task ID (auto-generated if not provided)

        Returns:
            Task ID
        """
        task_id = task_id or f"task_{uuid.uuid4().hex[:12]}"

        info = TaskInfo(
            id=task_id,
            name=task.name,
            status=TaskStatus.PENDING,
            priority=task.priority,
            created_at=datetime.now(),
            can_cancel=task.can_cancel
        )

        context = TaskContext(task_id, self)
        future: asyncio.Future = asyncio.get_event_loop().create_future()

        async with self._lock:
            self._tasks[task_id] = info
            self._contexts[task_id] = context
            self._futures[task_id] = future

            # Priority queue item: (priority, timestamp, task_id, task)
            # Lower priority value = higher priority
            await self._pending.put((
                -task.priority.value,  # Negative for proper ordering
                time.time(),
                task_id,
                task
            ))

        logger.debug(f"Task submitted: {task_id} ({task.name})")
        return task_id

    async def submit_async(
        self,
        coro: Coroutine,
        name: str = "async_task",
        priority: TaskPriority = TaskPriority.NORMAL,
        timeout: float = None
    ) -> str:
        """
        Submit an async coroutine as a task.

        Args:
            coro: Coroutine to execute
            name: Task name
            priority: Task priority
            timeout: Task timeout

        Returns:
            Task ID
        """
        class CoroutineTask(Task):
            def __init__(self, coro, name, priority, timeout):
                super().__init__(name, priority, timeout)
                self._coro = coro

            async def execute(self, context: TaskContext) -> Any:
                return await self._coro

        task = CoroutineTask(coro, name, priority, timeout)
        return await self.submit(task)

    async def submit_callable(
        self,
        fn: Callable,
        *args,
        name: str = "callable_task",
        priority: TaskPriority = TaskPriority.NORMAL,
        **kwargs
    ) -> str:
        """
        Submit a callable as a task.

        Args:
            fn: Callable to execute
            args: Positional arguments
            name: Task name
            priority: Task priority
            kwargs: Keyword arguments

        Returns:
            Task ID
        """
        class CallableTask(Task):
            def __init__(self, fn, args, kwargs, name, priority):
                super().__init__(name, priority)
                self._fn = fn
                self._args = args
                self._kwargs = kwargs

            async def execute(self, context: TaskContext) -> Any:
                if asyncio.iscoroutinefunction(self._fn):
                    return await self._fn(*self._args, **self._kwargs)
                else:
                    return await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: self._fn(*self._args, **self._kwargs)
                    )

        task = CallableTask(fn, args, kwargs, name, priority)
        return await self.submit(task)

    async def cancel(self, task_id: str) -> bool:
        """
        Cancel a task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancellation was requested
        """
        async with self._lock:
            if task_id not in self._tasks:
                return False

            info = self._tasks[task_id]
            context = self._contexts.get(task_id)

            if not info.can_cancel:
                logger.warning(f"Task {task_id} cannot be cancelled")
                return False

            if info.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                return False

            if context:
                context._request_cancel()

            info.status = TaskStatus.CANCELLED
            info.completed_at = datetime.now()

            if task_id in self._futures:
                future = self._futures[task_id]
                if not future.done():
                    future.cancel()

            logger.info(f"Task cancelled: {task_id}")
            return True

    async def cancel_all(self) -> int:
        """Cancel all pending and running tasks"""
        count = 0
        for task_id in list(self._tasks.keys()):
            if await self.cancel(task_id):
                count += 1
        return count

    async def wait_for(
        self,
        task_id: str,
        timeout: float = None
    ) -> TaskResult:
        """
        Wait for a task to complete.

        Args:
            task_id: Task ID
            timeout: Optional timeout

        Returns:
            TaskResult
        """
        if task_id not in self._futures:
            raise ValueError(f"Unknown task: {task_id}")

        future = self._futures[task_id]

        try:
            if timeout:
                result = await asyncio.wait_for(future, timeout)
            else:
                result = await future
            return result
        except asyncio.TimeoutError:
            await self.cancel(task_id)
            info = self._tasks[task_id]
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.TIMEOUT,
                error="Task timed out"
            )
        except asyncio.CancelledError:
            info = self._tasks[task_id]
            return TaskResult(
                task_id=task_id,
                status=TaskStatus.CANCELLED
            )

    def get_task_info(self, task_id: str) -> Optional[TaskInfo]:
        """Get information about a task"""
        return self._tasks.get(task_id)

    def get_all_tasks(self) -> List[TaskInfo]:
        """Get information about all tasks"""
        return list(self._tasks.values())

    def get_running_tasks(self) -> List[TaskInfo]:
        """Get information about running tasks"""
        return [
            info for info in self._tasks.values()
            if info.status == TaskStatus.RUNNING
        ]

    def get_pending_count(self) -> int:
        """Get number of pending tasks"""
        return self._pending.qsize()

    def get_running_count(self) -> int:
        """Get number of running tasks"""
        return len(self._running)

    def _update_task_progress(
        self,
        task_id: str,
        progress: float,
        message: str
    ) -> None:
        """Update task progress"""
        if task_id in self._tasks:
            self._tasks[task_id].progress = progress
            self._tasks[task_id].progress_message = message

    async def _worker_loop(self) -> None:
        """Main worker loop that executes tasks"""
        while not self._stopping:
            try:
                # Wait for available slot
                while len(self._running) >= self.max_concurrent:
                    await asyncio.sleep(0.1)
                    if self._stopping:
                        return

                # Get next task
                try:
                    _, _, task_id, task = await asyncio.wait_for(
                        self._pending.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue

                # Execute task
                self._running.add(task_id)
                asyncio.create_task(self._execute_task(task_id, task))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker loop error: {e}")
                await asyncio.sleep(1.0)

    async def _execute_task(self, task_id: str, task: Task) -> None:
        """Execute a single task"""
        info = self._tasks[task_id]
        context = self._contexts[task_id]
        future = self._futures[task_id]

        info.status = TaskStatus.RUNNING
        info.started_at = datetime.now()

        result = TaskResult(
            task_id=task_id,
            status=TaskStatus.PENDING,
            started_at=info.started_at
        )

        try:
            # Execute with timeout
            timeout = task.timeout or self.default_timeout

            try:
                task_result = await asyncio.wait_for(
                    task.execute(context),
                    timeout=timeout
                )
                result.status = TaskStatus.COMPLETED
                result.result = task_result
                info.status = TaskStatus.COMPLETED
            except asyncio.TimeoutError:
                result.status = TaskStatus.TIMEOUT
                result.error = f"Task timed out after {timeout}s"
                info.status = TaskStatus.TIMEOUT
                info.error = result.error
            except asyncio.CancelledError:
                result.status = TaskStatus.CANCELLED
                info.status = TaskStatus.CANCELLED
                await task.on_cancel()

        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error = str(e)
            info.status = TaskStatus.FAILED
            info.error = str(e)
            logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            await task.on_error(e)

        finally:
            # Cleanup
            result.completed_at = datetime.now()
            info.completed_at = result.completed_at
            result.execution_time_ms = (
                (result.completed_at - result.started_at).total_seconds() * 1000
            )
            info.progress = 1.0

            await task.cleanup()

            self._running.discard(task_id)

            if not future.done():
                future.set_result(result)

            logger.debug(
                f"Task {task_id} completed: {result.status.value} "
                f"({result.execution_time_ms:.1f}ms)"
            )


# ============== SCHEDULED TASKS ==============

class ScheduledTask:
    """Task scheduled to run at intervals"""

    def __init__(
        self,
        task: Task,
        interval: float,
        start_immediately: bool = True
    ):
        self.task = task
        self.interval = interval
        self.start_immediately = start_immediately

        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self, manager: TaskManager) -> None:
        """Start the scheduled task"""
        self._running = True
        self._task = asyncio.create_task(self._run_loop(manager))

    async def stop(self) -> None:
        """Stop the scheduled task"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self, manager: TaskManager) -> None:
        """Run the task at intervals"""
        if not self.start_immediately:
            await asyncio.sleep(self.interval)

        while self._running:
            try:
                task_id = await manager.submit(self.task)
                await manager.wait_for(task_id)
            except Exception as e:
                logger.error(f"Scheduled task error: {e}")

            if self._running:
                await asyncio.sleep(self.interval)


# ============== SINGLETON ==============

_task_manager: Optional[TaskManager] = None


def get_task_manager() -> TaskManager:
    """Get or create the global task manager"""
    global _task_manager

    if _task_manager is None:
        _task_manager = TaskManager()

    return _task_manager


async def init_task_manager(max_concurrent: int = 10) -> TaskManager:
    """Initialize and start the global task manager"""
    global _task_manager

    if _task_manager is None:
        _task_manager = TaskManager(max_concurrent=max_concurrent)
        await _task_manager.start()

    return _task_manager


async def shutdown_task_manager() -> None:
    """Shutdown the global task manager"""
    global _task_manager

    if _task_manager:
        await _task_manager.stop()
        _task_manager = None
