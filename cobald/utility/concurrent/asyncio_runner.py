import asyncio
import time
from functools import partial

from .base_runner import BaseRunner
from .async_tools import raise_return, AsyncExecution


class AsyncioRunner(BaseRunner):
    flavour = asyncio

    def __init__(self):
        super().__init__()
        self.event_loop = asyncio.new_event_loop()
        self._tasks = set()

    def register_payload(self, payload):
        super().register_payload(partial(raise_return, payload))

    def run_payload(self, payload):
        execution = AsyncExecution(payload)
        super().register_payload(execution.coroutine)
        return execution.wait()

    def _run(self):
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.run_until_complete(self.await_all())

    async def await_all(self):
        try:
            while self.running.is_set():
                await self._start_outstanding()
                await self._manage_running()
                await asyncio.sleep(1)
        except Exception:
            await self._cancel_running()
            raise

    async def _start_outstanding(self):
        with self._lock:
            for coroutine in self._payloads:
                task = self.event_loop.create_task(coroutine())
                self._tasks.add(task)
            self._payloads.clear()
        await asyncio.sleep(0)

    async def _manage_running(self):
        for task in self._tasks.copy():
            if task.done():
                self._tasks.remove(task)
                if task.exception() is not None:
                    raise task.exception()
        await asyncio.sleep(0)

    async def _cancel_running(self):
        for task in self._tasks:
            task.cancel()
            await asyncio.sleep(0)
        for task in self._tasks:
            while not task.done():
                await asyncio.sleep(0.1)

    def stop(self):
        with self._lock:
            self.running.clear()
            for task in self._tasks:
                task.cancel()
        self._stopped.wait()
        self.event_loop.stop()
        self.event_loop.close()
