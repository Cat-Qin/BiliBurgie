"""Async worker thread running the event loop for backend services."""
from __future__ import annotations
import asyncio
import logging
from typing import Optional
from PyQt5.QtCore import QThread, pyqtSignal
from ..core.event_processor import EventProcessor
from ..platforms.bilibili_listener import BilibiliListener
from ..utils.config_loader import get_config

logger = logging.getLogger("BurgerRelay.worker")


class AsyncWorker(QThread):
    irc_status = pyqtSignal(bool)
    bilibili_status = pyqtSignal(bool)
    llm_status = pyqtSignal(object)  # True/False/None

    def __init__(self, processor: EventProcessor) -> None:
        super().__init__()
        self._processor = processor
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._bili: Optional[BilibiliListener] = None

    # ------------------------------------------------------------------
    # Thread lifecycle
    # ------------------------------------------------------------------

    def run(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.set_exception_handler(self._on_loop_error)
        try:
            self._loop.run_until_complete(self._run())
        except asyncio.CancelledError:
            # Normal shutdown via loop.stop()
            pass
        except Exception:
            logger.exception("Async worker crashed")
        finally:
            self._loop.run_until_complete(self._loop.shutdown_asyncgens())
            self._loop.close()
            logger.debug("Event loop closed")

    def _on_loop_error(self, loop, context) -> None:
        """Handle asyncio errors. Use print() to avoid Qt objects being GC'd."""
        exc = context.get("exception")
        msg = context.get("message", str(exc or ""))
        print(f"[BurgerRelay] Async loop error: {msg}", flush=True)
        if exc:
            print(f"[BurgerRelay] {exc}", flush=True)

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def _run(self) -> None:
        """Main coroutine that runs until the event loop is stopped."""
        await self._processor.start()
        self.irc_status.emit(True)
        self._processor.irc.set_client_change_callback(
            lambda c: self.irc_status.emit(c))

        config = get_config()
        b = config.get("bilibili", {})
        if b.get("room_id", 0) > 0:
            self._bili = BilibiliListener(
                b["room_id"],
                self._processor.handle_event,
                sessdata=b.get("sessdata", ""),
                bili_jct=b.get("bili_jct", ""),
                buvid3=b.get("buvid3", ""),
            )
            asyncio.create_task(self._start_bilibili())

        # Test LLM connectivity
        asyncio.create_task(self._test_llm(config))

        # Idle until shutdown — loop.stop() will end run_forever / this coroutine
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    async def _test_llm(self, config: dict) -> None:
        """Test LLM connectivity and emit status."""
        llm_cfg = config.get("llm", {})
        if not llm_cfg.get("enabled", True):
            self.llm_status.emit(None)
            return

        from ..llm.llm_factory import create_llm_client
        client = create_llm_client(
            llm_cfg.get("provider", "custom"),
            llm_cfg.get("model", ""),
            llm_cfg.get("api_base", ""),
            llm_cfg.get("api_key", ""),
            llm_cfg.get("temperature", 0.1),
            llm_cfg.get("timeout", 5.0),
            llm_cfg.get("max_tokens", 300),
        )
        if client is None:
            self.llm_status.emit(False)
            return

        try:
            ok = await client.test()
            self.llm_status.emit(ok)
        except Exception:
            self.llm_status.emit(False)

    async def _start_bilibili(self) -> None:
        try:
            await self._bili.start()
            self.bilibili_status.emit(True)
        except Exception as e:
            logger.error(f"B站 listener failed: {e}")
            self.bilibili_status.emit(False)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def stop_worker(self) -> None:
        """Signal the worker to stop from the main thread."""
        fut = None
        if self._loop and self._loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(self._shutdown(), self._loop)
        # Wait for the thread to finish (with generous timeout)
        if not self.wait(10000):
            logger.warning("Worker thread did not finish within 10s")
        # Consume the future result to avoid "Task was destroyed but pending"
        if fut:
            try:
                fut.result(timeout=5)
            except Exception:
                pass

    async def _shutdown(self) -> None:
        """Gracefully stop all services and the event loop."""
        try:
            if self._bili:
                await self._bili.stop()
        except Exception:
            logger.exception("Error stopping B站 listener")

        try:
            await self._processor.stop()
        except Exception:
            logger.exception("Error stopping processor")

        # Cancel remaining tasks (except self) and let them settle
        for t in asyncio.all_tasks():
            if t is not asyncio.current_task():
                t.cancel()

        # Give cancelled tasks one tick to process cancellation
        await asyncio.sleep(0)

        # Stop the loop — run_until_complete will return, then finally: closes it
        self._loop.stop()
        logger.info("Shutdown complete")
