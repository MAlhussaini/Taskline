#!/usr/bin/env python3
"""Responsive browser smoke test for Taskline's full-month calendar."""

from __future__ import annotations

import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket


APP_URL = "http://100.109.102.8:8000/"
VIEWPORTS = ((320, 568), (568, 320), (768, 1024), (1440, 900))


class DevTools:
    def __init__(self, socket: websocket.WebSocket) -> None:
        self.socket = socket
        self.next_id = 1

    def call(self, method: str, params: dict | None = None) -> dict:
        message_id = self.next_id
        self.next_id += 1
        self.socket.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
        while True:
            response = json.loads(self.socket.recv())
            if response.get("id") != message_id:
                continue
            if "error" in response:
                raise AssertionError(f"{method}: {response['error']}")
            return response.get("result", {})

    def evaluate(self, expression: str):
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        if result.get("exceptionDetails"):
            raise AssertionError(result["exceptionDetails"])
        return result["result"].get("value")


def wait_for(predicate, timeout: float = 10) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise TimeoutError("Timed out waiting for browser state")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="taskline-chrome-") as profile:
        process = subprocess.Popen(
            [
                "/usr/bin/google-chrome",
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--remote-allow-origins=*",
                "--remote-debugging-port=0",
                f"--user-data-dir={profile}",
                APP_URL,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            port_file = Path(profile, "DevToolsActivePort")
            wait_for(port_file.exists)
            port = port_file.read_text().splitlines()[0]

            def page_target():
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list", timeout=2) as response:
                    return next((item for item in json.load(response) if item["type"] == "page"), None)

            target = None

            def browser_page_is_ready() -> bool:
                nonlocal target
                target = page_target()
                return target is not None

            wait_for(browser_page_is_ready)
            assert target is not None
            socket = websocket.create_connection(target["webSocketDebuggerUrl"], timeout=10)
            devtools = DevTools(socket)
            devtools.call("Runtime.enable")
            wait_for(lambda: devtools.evaluate("document.readyState === 'complete' && Boolean(window.TasklineCalendar)"))
            devtools.evaluate("document.querySelector('#month-picker').click()")
            wait_for(lambda: devtools.evaluate("document.querySelector('#month-dialog').open && document.querySelectorAll('.month-day').length === 42"))

            for width, height in VIEWPORTS:
                devtools.call(
                    "Emulation.setDeviceMetricsOverride",
                    {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": width <= 600},
                )
                time.sleep(0.15)
                metrics = devtools.evaluate(
                    """(() => {
                      const dialog = document.querySelector('#month-dialog');
                      const grid = document.querySelector('#month-grid');
                      const rect = dialog.getBoundingClientRect();
                      const dayRects = [...grid.querySelectorAll('.month-day')].map(day => day.getBoundingClientRect());
                      return {
                        open: dialog.open,
                        days: grid.querySelectorAll('.month-day').length,
                        insideViewport: rect.left >= -1 && rect.right <= innerWidth + 1 && rect.top >= -1 && rect.bottom <= innerHeight + 1,
                        pageFits: document.documentElement.scrollWidth <= innerWidth,
                        gridFits: grid.scrollWidth <= grid.clientWidth,
                        minDayWidth: Math.min(...dayRects.map(day => day.width)),
                        minDayHeight: Math.min(...dayRects.map(day => day.height)),
                      };
                    })()"""
                )
                assert metrics["open"] is True, (width, height, metrics)
                assert metrics["days"] == 42, (width, height, metrics)
                assert metrics["insideViewport"] is True, (width, height, metrics)
                assert metrics["pageFits"] is True, (width, height, metrics)
                assert metrics["gridFits"] is True, (width, height, metrics)
                if width <= 360:
                    assert metrics["minDayWidth"] >= 43, (width, height, metrics)
                    assert metrics["minDayHeight"] >= 44, (width, height, metrics)

            moved_with_keyboard = devtools.evaluate(
                """(() => {
                  const selected = document.querySelector('.month-day.selected');
                  const expected = TasklineCalendar.addDays(selected.dataset.date, 1);
                  selected.focus();
                  selected.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
                  return document.activeElement.dataset.date === expected;
                })()"""
            )
            assert moved_with_keyboard is True

            devtools.evaluate("document.querySelector('#language-toggle').click()")
            rtl = devtools.evaluate("document.documentElement.dir === 'rtl' && document.querySelector('#month-dialog').open")
            assert rtl is True
            socket.close()
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()
