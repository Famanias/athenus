import asyncio
from dataclasses import dataclass
from typing import Callable, Coroutine, Any, List

@dataclass
class HardwareSpecs:
    cpu_cores: int = 4
    total_ram_mb: int = 16384
    has_gpu: bool = False
    vram_available_mb: int = 0

class WorkloadScheduler:
    """Workload Scheduler acting as local OS for AI tasks & concurrency throttling."""
    def __init__(self, max_concurrent_tasks: int = 2) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.specs = HardwareSpecs()
        self._detect_hardware()

    def _detect_hardware(self) -> None:
        import os
        self.specs.cpu_cores = os.cpu_count() or 4
        # Additional hardware auto-detection (e.g. torch / pynvml) can be attached here

    async def submit_task(self, task_name: str, task_func: Callable[[], Coroutine[Any, Any, Any]]) -> Any:
        async with self._semaphore:
            return await task_func()

workload_scheduler = WorkloadScheduler()
