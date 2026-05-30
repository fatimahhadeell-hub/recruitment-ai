
import threading
import time
import datetime
from typing import Optional
from loguru import logger
from config.settings import settings
from intake.drive_fetcher import DriveFetcher

class CVPoller:
    def __init__(self):
        self._thread           = None
        self._stop_event       = threading.Event()
        self._total_cycles     = 0
        self._total_new_cvs    = 0
        self._total_errors     = 0
        self._last_run_at      = None
        self._last_run_result  = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            logger.warning("CVPoller already running.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="CVPoller", daemon=True)
        self._thread.start()
        logger.success(f"CVPoller started. Checking every {settings.GOOGLE_POLL_INTERVAL_SECONDS} seconds.")

    def stop(self) -> None:
        if not self._thread or not self._thread.is_alive():
            return
        logger.info("CVPoller stopping...")
        self._stop_event.set()
        self._thread.join(timeout=10)
        logger.info("CVPoller stopped.")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def status(self) -> dict:
        return {
            "running":               self.is_running(),
            "total_cycles":          self._total_cycles,
            "total_new_cvs":         self._total_new_cvs,
            "total_errors":          self._total_errors,
            "last_run_at":           self._last_run_at.isoformat() if self._last_run_at else None,
            "last_run_result":       self._last_run_result,
            "poll_interval_seconds": settings.GOOGLE_POLL_INTERVAL_SECONDS,
        }

    def run_now(self) -> dict:
        logger.info("Manual fetch triggered.")
        fetcher = DriveFetcher()
        result  = fetcher.run()
        self._update_stats(result)
        return result

    def _poll_loop(self) -> None:
        logger.info("CVPoller loop started.")
        while not self._stop_event.is_set():
            self._run_single_cycle()
            for _ in range(settings.GOOGLE_POLL_INTERVAL_SECONDS):
                if self._stop_event.is_set():
                    break
                time.sleep(1)
        logger.info("CVPoller loop exited.")

    def _run_single_cycle(self) -> None:
        logger.info(f"CVPoller: Starting fetch cycle {self._total_cycles + 1}...")
        try:
            fetcher = DriveFetcher()
            result  = fetcher.run()
            self._update_stats(result)
        except Exception as e:
            logger.error(f"CVPoller unhandled error: {e}", exc_info=True)
            self._total_errors += 1

    def _update_stats(self, result: dict) -> None:
        self._total_cycles   += 1
        self._total_new_cvs  += result.get("new", 0)
        self._total_errors   += result.get("errors", 0)
        self._last_run_at     = datetime.datetime.utcnow()
        self._last_run_result = result

cv_poller = CVPoller()
