#!/usr/bin/env python3
"""
Read RFID UIDs from an Arduino over serial and switch videos on a Raspberry Pi.

Expected serial line format from Arduino:
    UID:04A1B2C3D4
"""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import serial
import serial.serialutil


def normalize_uid(raw: str) -> str:
    return "".join(ch for ch in raw.upper() if ch in "0123456789ABCDEF")


@dataclass
class RuntimeConfig:
    serial_port: str
    baud_rate: int
    read_timeout: float
    switch_cooldown_seconds: float
    media_root: Path
    default_video: str | None
    player_command: list[str]
    video_map: dict[str, str]


def load_config(config_path: Path) -> RuntimeConfig:
    with config_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    media_root_value = data.get("media_root", ".")
    media_root = (config_path.parent / media_root_value).resolve()

    raw_map: dict[str, str] = data.get("video_map", {})
    normalized_map = {normalize_uid(uid): value for uid, value in raw_map.items()}

    command = data.get("player", {}).get("command", ["cvlc", "--fullscreen", "--loop", "{video}"])
    if not isinstance(command, list) or not all(isinstance(part, str) for part in command):
        raise ValueError("player.command must be a list of strings")

    return RuntimeConfig(
        serial_port=str(data.get("serial_port", "/dev/ttyACM0")),
        baud_rate=int(data.get("baud_rate", 115200)),
        read_timeout=float(data.get("read_timeout", 0.2)),
        switch_cooldown_seconds=float(data.get("switch_cooldown_seconds", 1.0)),
        media_root=media_root,
        default_video=data.get("default_video"),
        player_command=command,
        video_map=normalized_map,
    )


class VideoSwitcher:
    def __init__(self, cfg: RuntimeConfig, learn_tags_only: bool = False) -> None:
        self.cfg = cfg
        self.learn_tags_only = learn_tags_only
        self.current_uid: str | None = None
        self.current_video: Path | None = None
        self.last_switch_ts = 0.0
        self.player_process: subprocess.Popen[bytes] | None = None
        self.running = True

    def stop(self) -> None:
        self.running = False
        self._stop_player()

    def run(self) -> None:
        if not self.learn_tags_only and self.cfg.default_video:
            self._switch_to_video(self.cfg.default_video)

        while self.running:
            try:
                with serial.Serial(
                    self.cfg.serial_port,
                    self.cfg.baud_rate,
                    timeout=self.cfg.read_timeout,
                ) as ser:
                    print(f"[serial] Connected to {self.cfg.serial_port} @ {self.cfg.baud_rate}")
                    self._read_loop(ser)
            except serial.serialutil.SerialException as exc:
                print(f"[serial] Waiting for device {self.cfg.serial_port}: {exc}")
                time.sleep(1.0)

    def _read_loop(self, ser: serial.Serial) -> None:
        while self.running:
            raw = ser.readline()
            if not raw:
                continue

            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                continue

            if not line.startswith("UID:"):
                print(f"[serial] {line}")
                continue

            uid = normalize_uid(line.removeprefix("UID:"))
            if not uid:
                continue

            print(f"[tag] {uid}")

            if self.learn_tags_only:
                continue

            target_video = self.cfg.video_map.get(uid)
            if not target_video:
                print(f"[map] No video mapped for UID {uid}")
                continue

            now = time.time()
            if uid == self.current_uid and (now - self.last_switch_ts) < self.cfg.switch_cooldown_seconds:
                continue

            self.current_uid = uid
            self.last_switch_ts = now
            self._switch_to_video(target_video)

    def _resolve_video(self, video_value: str) -> Path:
        candidate = Path(video_value)
        if candidate.is_absolute():
            return candidate
        return (self.cfg.media_root / candidate).resolve()

    def _switch_to_video(self, video_value: str) -> None:
        video_path = self._resolve_video(video_value)
        if not video_path.exists():
            print(f"[video] Missing file: {video_path}")
            return

        if self.current_video == video_path:
            return

        self._stop_player()

        command = [part.replace("{video}", str(video_path)) for part in self.cfg.player_command]
        print(f"[video] Switching to {video_path.name}")
        try:
            self.player_process = subprocess.Popen(command)
        except FileNotFoundError as exc:
            print(f"[player] Player executable not found: {exc}")
            print("[player] Install VLC (`sudo apt install vlc`) or update player.command in config.")
            self.running = False
            return
        self.current_video = video_path

    def _stop_player(self) -> None:
        if not self.player_process:
            return

        if self.player_process.poll() is None:
            self.player_process.terminate()
            try:
                self.player_process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.player_process.kill()

        self.player_process = None


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="RFID to video switcher for Raspberry Pi")
    parser.add_argument(
        "--config",
        default="pi/tag_video_map.json",
        help="Path to JSON config file (default: pi/tag_video_map.json)",
    )
    parser.add_argument(
        "--learn-tags",
        action="store_true",
        help="Only print detected UIDs, do not switch videos",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    cfg = load_config(Path(args.config).resolve())

    switcher = VideoSwitcher(cfg, learn_tags_only=args.learn_tags)

    def _handle_signal(signum: int, _frame: Any) -> None:
        print(f"\n[signal] Stopping (signal {signum})")
        switcher.stop()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        switcher.run()
    finally:
        switcher.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
