#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
灵枢（LingShu）Agent — 任务调度器测试
覆盖：TaskScheduler、Task、TaskTrigger、TaskConfig
"""

import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.scheduler import (
    TaskScheduler,
    Task,
    TaskTrigger,
    TaskConfig,
    TaskState,
    TaskPriority,
    TriggerType,
)


@pytest.fixture
def scheduler():
    """创建临时调度器"""
    with tempfile.TemporaryDirectory() as tmp:
        s = TaskScheduler(persistence_path=Path(tmp) / "tasks.json")
        yield s
        s.stop()


class TestTaskTrigger:
    """测试任务触发器"""

    def test_immediate_trigger(self):
        trigger = TaskTrigger(type=TriggerType.IMMEDIATE)
        assert trigger.should_trigger(last_execution=0, execution_count=0) == True
        assert trigger.should_trigger(last_execution=1.0, execution_count=1) == False

    def test_delay_trigger(self):
        trigger = TaskTrigger(type=TriggerType.DELAY, delay_seconds=1.0)
        assert trigger.should_trigger(last_execution=0, execution_count=0) == True
        # 尚未到达延迟时间
        assert trigger.should_trigger(last_execution=time.time(), execution_count=1) == False

    def test_interval_trigger(self):
        trigger = TaskTrigger(type=TriggerType.INTERVAL, interval_seconds=0.1)
        assert trigger.should_trigger(last_execution=0, execution_count=0) == True

    def test_once_trigger(self):
        trigger = TaskTrigger(type=TriggerType.ONCE, execute_at=time.time() + 10)
        assert trigger.should_trigger(last_execution=0, execution_count=0) == False

        trigger2 = TaskTrigger(type=TriggerType.ONCE, execute_at=time.time() - 1)
        assert trigger2.should_trigger(last_execution=0, execution_count=0) == True

    def test_max_executions(self):
        trigger = TaskTrigger(type=TriggerType.IMMEDIATE, max_executions=2)
        assert trigger.should_trigger(last_execution=0, execution_count=0) == True
        assert trigger.should_trigger(last_execution=0, execution_count=1) == True
        assert trigger.should_trigger(last_execution=0, execution_count=2) == False

    def test_next_trigger_time(self):
        trigger = TaskTrigger(type=TriggerType.DELAY, delay_seconds=5.0)
        next_t = trigger.next_trigger_time(last_execution=100.0)
        assert next_t == 105.0

        trigger2 = TaskTrigger(type=TriggerType.INTERVAL, interval_seconds=10.0)
        next_t2 = trigger2.next_trigger_time(last_execution=0)
        assert next_t2 is not None


class TestTask:
    """测试任务对象"""

    def test_create_task(self):
        def dummy_func():
            return 42

        trigger = TaskTrigger(type=TriggerType.IMMEDIATE)
        task = Task("test_task", dummy_func, trigger)
        assert task.name == "test_task"
        assert task.record.state == TaskState.PENDING
        assert task.task_id != ""

    def test_run_task(self):
        def success_func():
            return "ok"

        trigger = TaskTrigger(type=TriggerType.IMMEDIATE)
        task = Task("success", success_func, trigger)
        result = task.run()
        assert result == "ok"
        assert task.record.state == TaskState.COMPLETED
        assert task.record.execution_count == 1

    def test_run_task_exception(self):
        def fail_func():
            raise ValueError("boom")

        trigger = TaskTrigger(type=TriggerType.IMMEDIATE)
        task = Task("fail", fail_func, trigger)
        with pytest.raises(ValueError):
            task.run()
        assert task.record.state == TaskState.FAILED

    def test_cancel_task(self):
        def dummy():
            pass

        trigger = TaskTrigger(type=TriggerType.IMMEDIATE)
        task = Task("cancel", dummy, trigger)
        assert task.cancel() == True
        assert task.record.state == TaskState.CANCELLED

        # 已取消的任务再次取消应返回 False
        assert task.cancel() == False

    def test_pause_resume(self):
        def dummy():
            pass

        trigger = TaskTrigger(type=TriggerType.IMMEDIATE)
        task = Task("pause", dummy, trigger)
        assert task.pause() == True
        assert task.record.state == TaskState.PAUSED
        assert task.resume() == True
        assert task.record.state == TaskState.PENDING


class TestTaskScheduler:
    """测试任务调度器"""

    def test_add_task(self, scheduler):
        def work():
            return "done"

        trigger = TaskTrigger(type=TriggerType.IMMEDIATE)
        task = scheduler.add_task("work", work, trigger)
        assert task.task_id in scheduler._tasks
        assert scheduler._task_states[task.task_id] == TaskState.PENDING

    def test_remove_task(self, scheduler):
        def work():
            pass

        trigger = TaskTrigger(type=TriggerType.IMMEDIATE)
        task = scheduler.add_task("work", work, trigger)
        assert scheduler.remove_task(task.task_id) == True
        assert task.task_id not in scheduler._tasks

    def test_get_task(self, scheduler):
        def work():
            pass

        trigger = TaskTrigger(type=TriggerType.IMMEDIATE)
        task = scheduler.add_task("work", work, trigger)
        found = scheduler.get_task(task.task_id)
        assert found is not None
        assert found.name == "work"

    def test_list_tasks(self, scheduler):
        def work1():
            pass

        def work2():
            pass

        scheduler.add_task("w1", work1, TaskTrigger(type=TriggerType.IMMEDIATE))
        scheduler.add_task("w2", work2, TaskTrigger(type=TriggerType.IMMEDIATE))
        tasks = scheduler.list_tasks()
        assert len(tasks) == 2

    def test_list_tasks_by_state(self, scheduler):
        def work():
            pass

        task = scheduler.add_task("w", work, TaskTrigger(type=TriggerType.IMMEDIATE))
        task.run()
        tasks = scheduler.list_tasks(TaskState.COMPLETED)
        assert len(tasks) == 1

    def test_schedule_interval(self, scheduler):
        result = {"count": 0}

        def counter():
            result["count"] += 1
            return result["count"]

        task = scheduler.schedule_interval("counter", counter, 0.1)
        assert task is not None
        assert task.trigger.type == TriggerType.INTERVAL
        assert task.trigger.interval_seconds == 0.1

    def test_schedule_delay(self, scheduler):
        result = {"done": False}

        def delayed():
            result["done"] = True
            return "done"

        task = scheduler.schedule_delay("delayed", delayed, 0.05)
        assert task is not None
        assert task.trigger.type == TriggerType.DELAY
        assert task.trigger.delay_seconds == 0.05

    def test_start_stop(self, scheduler):
        scheduler.start()
        assert scheduler._scheduler_running == True
        assert scheduler._scheduler_thread is not None
        scheduler.stop()
        assert scheduler._scheduler_running == False

    def test_task_config_defaults(self):
        config = TaskConfig()
        assert config.priority == TaskPriority.NORMAL
        assert config.max_retries == 3
        assert config.timeout_seconds == 300.0

    def test_task_config_priority(self):
        config = TaskConfig(priority=TaskPriority.CRITICAL, max_retries=0)
        assert config.priority == TaskPriority.CRITICAL
        assert config.max_retries == 0

    def test_persistence(self, scheduler):
        def work():
            return 1

        scheduler.add_task("work", work, TaskTrigger(type=TriggerType.IMMEDIATE))
        # 持久化后重新加载
        scheduler._persist()
        assert scheduler.persistence_path.exists()

    def test_concurrent_task_add(self, scheduler):
        results = []
        lock = threading.Lock()

        def work(n):
            with lock:
                results.append(n)
            return n

        for i in range(10):
            scheduler.add_task(
                f"work_{i}",
                lambda i=i: work(i),
                TaskTrigger(type=TriggerType.IMMEDIATE),
            )

        assert len(scheduler._tasks) == 10

    def test_cancel_task(self, scheduler):
        def work():
            return 1

        task = scheduler.add_task("work", work, TaskTrigger(type=TriggerType.IMMEDIATE))
        assert scheduler.cancel_task(task.task_id) == True
        assert task.record.state == TaskState.CANCELLED

    def test_pause_resume_task(self, scheduler):
        def work():
            return 1

        task = scheduler.add_task("work", work, TaskTrigger(type=TriggerType.IMMEDIATE))
        assert scheduler.pause_task(task.task_id) == True
        assert task.record.state == TaskState.PAUSED
        assert scheduler.resume_task(task.task_id) == True
        assert task.record.state == TaskState.PENDING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
