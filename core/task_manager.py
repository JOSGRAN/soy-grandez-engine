from __future__ import annotations
# ... resto de las importaciones

import asyncio
import time
from enum import Enum
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from core.exceptions import RetryableException, NonRetryableException, TimeoutException
from core.logger import get_logger

logger = get_logger("task_manager")


class TaskStatus(Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


@dataclass
class TaskResult:
    """Result of a task execution."""
    success: bool
    data: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    retry_count: int = 0
    status: TaskStatus = TaskStatus.PENDING


@dataclass
class Task:
    """Represents a unit of work to be executed."""
    id: str
    name: str
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    max_retries: int = 3
    retry_delay: int = 5
    timeout: int = 300
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[TaskResult] = None
    dependencies: List[str] = field(default_factory=list)
    
    def can_execute(self, completed_tasks: Dict[str, Task]) -> bool:
        """Check if task dependencies are satisfied."""
        for dep_id in self.dependencies:
            dep_task = completed_tasks.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True


class TaskManager:
    """Manages task execution with retry logic and dependency handling."""
    
    def __init__(self, max_concurrent_tasks: int = 5):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}
        self.running_tasks: Dict[str, Task] = {}
        self._running = False
    
    def add_task(
        self,
        task_id: str,
        name: str,
        func: Callable,
        args: tuple = (),
        kwargs: dict = None,
        max_retries: int = 3,
        retry_delay: int = 5,
        timeout: int = 300,
        dependencies: List[str] = None
    ) -> Task:
        """Add a new task to the manager."""
        if kwargs is None:
            kwargs = {}
        if dependencies is None:
            dependencies = []
        
        task = Task(
            id=task_id,
            name=name,
            func=func,
            args=args,
            kwargs=kwargs,
            max_retries=max_retries,
            retry_delay=retry_delay,
            timeout=timeout,
            dependencies=dependencies
        )
        
        self.tasks[task_id] = task
        logger.info(f"Task added: {task_id} - {name}")
        return task
    
    async def execute_task(self, task: Task) -> TaskResult:
        """Execute a single task with retry logic."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.running_tasks[task.id] = task
        
        retry_count = 0
        last_error = None
        
        while retry_count <= task.max_retries:
            try:
                logger.info(f"Executing task: {task.id} - {task.name} (Attempt {retry_count + 1})")
                
                # Execute with timeout
                result_data = await asyncio.wait_for(
                    task.func(*task.args, **task.kwargs),
                    timeout=task.timeout
                )
                
                # Task completed successfully
                task.completed_at = datetime.now()
                execution_time = (task.completed_at - task.started_at).total_seconds()
                
                task_result = TaskResult(
                    success=True,
                    data=result_data,
                    execution_time=execution_time,
                    retry_count=retry_count,
                    status=TaskStatus.COMPLETED
                )
                
                task.result = task_result
                task.status = TaskStatus.COMPLETED
                
                logger.info(f"Task completed successfully: {task.id} - {task.name} (Time: {execution_time:.2f}s)")
                
                return task_result
                
            except asyncio.TimeoutError:
                last_error = f"Task timeout after {task.timeout} seconds"
                logger.error(f"Task timeout: {task.id} - {task.name}")
                
            except RetryableException as e:
                last_error = str(e)
                logger.warning(f"Retryable error in task {task.id}: {e}")
                
            except NonRetryableException as e:
                last_error = str(e)
                logger.error(f"Non-retryable error in task {task.id}: {e}")
                break  # Don't retry non-retryable exceptions
                
            except Exception as e:
                last_error = str(e)
                logger.error(f"Unexpected error in task {task.id}: {e}")
                
            # Retry logic
            if retry_count < task.max_retries:
                retry_count += 1
                task.status = TaskStatus.RETRYING
                logger.info(f"Retrying task {task.id} in {task.retry_delay} seconds... (Attempt {retry_count + 1})")
                await asyncio.sleep(task.retry_delay)
            else:
                break
        
        # Task failed after all retries
        task.completed_at = datetime.now()
        execution_time = (task.completed_at - task.started_at).total_seconds()
        
        task_result = TaskResult(
            success=False,
            error=last_error,
            execution_time=execution_time,
            retry_count=retry_count,
            status=TaskStatus.FAILED
        )
        
        task.result = task_result
        task.status = TaskStatus.FAILED
        
        logger.error(f"Task failed after {retry_count} retries: {task.id} - {task.name} - Error: {last_error}")
        
        return task_result
    
    async def execute_all(self) -> Dict[str, TaskResult]:
        """Execute all tasks respecting dependencies and concurrency limits."""
        if not self.tasks:
            logger.warning("No tasks to execute")
            return {}
        
        self._running = True
        results = {}
        
        while self.tasks and self._running:
            # Find tasks that can be executed (dependencies satisfied)
            executable_tasks = [
                task for task in self.tasks.values()
                if task.status == TaskStatus.PENDING and task.can_execute(self.completed_tasks)
            ]
            
            if not executable_tasks:
                # Check if we have running tasks
                if self.running_tasks:
                    await asyncio.sleep(1)
                    continue
                else:
                    # No executable tasks and no running tasks - circular dependency or error
                    logger.error("No executable tasks found - possible circular dependency")
                    break
            
            # Execute up to max_concurrent_tasks
            tasks_to_execute = executable_tasks[:self.max_concurrent_tasks]
            
            # Execute tasks concurrently
            execution_tasks = [
                self.execute_task(task) for task in tasks_to_execute
            ]
            
            task_results = await asyncio.gather(*execution_tasks, return_exceptions=True)
            
            # Process results
            for task, result in zip(tasks_to_execute, task_results):
                if isinstance(result, Exception):
                    logger.error(f"Task execution error: {task.id} - {result}")
                    result = TaskResult(success=False, error=str(result))
                
                results[task.id] = result
                
                # Move task to completed
                self.completed_tasks[task.id] = task
                del self.tasks[task.id]
                
                if task.id in self.running_tasks:
                    del self.running_tasks[task.id]
        
        self._running = False
        return results
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        if task_id in self.tasks:
            self.tasks[task_id].status = TaskStatus.CANCELLED
            logger.info(f"Task cancelled: {task_id}")
            return True
        return False
    
    def cancel_all(self):
        """Cancel all pending tasks."""
        for task in self.tasks.values():
            task.status = TaskStatus.CANCELLED
        logger.info("All pending tasks cancelled")
    
    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get the status of a specific task."""
        if task_id in self.tasks:
            return self.tasks[task_id].status
        elif task_id in self.completed_tasks:
            return self.completed_tasks[task_id].status
        elif task_id in self.running_tasks:
            return self.running_tasks[task_id].status
        return None
    
    def get_progress(self) -> Dict[str, Any]:
        """Get overall execution progress."""
        total_tasks = len(self.tasks) + len(self.completed_tasks) + len(self.running_tasks)
        completed = len(self.completed_tasks)
        running = len(self.running_tasks)
        failed = sum(1 for t in self.completed_tasks.values() if t.status == TaskStatus.FAILED)
        
        return {
            "total": total_tasks,
            "completed": completed,
            "running": running,
            "pending": len(self.tasks),
            "failed": failed,
            "progress_percent": (completed / total_tasks * 100) if total_tasks > 0 else 0
        }
    
    def stop(self):
        """Stop task execution."""
        self._running = False
        self.cancel_all()
        logger.info("Task manager stopped")
