from __future__ import annotations

import asyncio
from contextlib import suppress
import json
from abc import ABC, abstractmethod
from typing import Any, Optional


class RendererBridge(ABC):
    @abstractmethod
    async def connect(self, node_id: str, label: str) -> None: ...

    async def set_mapping(self, mapping_config: dict[str, Any]) -> None:
        return

    @abstractmethod
    async def load_show(self, show_id: str, payload: dict[str, Any]) -> None: ...

    @abstractmethod
    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None: ...

    @abstractmethod
    async def pause(self) -> None: ...

    @abstractmethod
    async def seek(self, position_ms: int) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def update_layers(self, layers: list[dict[str, Any]]) -> None: ...

    @abstractmethod
    async def hot_swap(self, layer_id: str, payload: dict[str, Any]) -> None: ...

    @abstractmethod
    async def ping(self) -> None: ...

    @abstractmethod
    async def tick(self, snapshot: dict[str, Any]) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...


class Decoder(ABC):
    @abstractmethod
    async def load_show(self, show_id: str, payload: dict[str, Any]) -> None: ...

    @abstractmethod
    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None: ...

    @abstractmethod
    async def get_next_frame(self, media_id: str) -> Optional[tuple[bytes, float]]: ...

    @abstractmethod
    async def close(self) -> None: ...


class NullDecoder(Decoder):
    async def load_show(self, show_id: str, payload: dict[str, Any]) -> None:
        return

    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None:
        return

    async def get_next_frame(self, media_id: str) -> Optional[tuple[bytes, float]]:
        return None

    async def close(self) -> None:
        return


class NullRendererBridge(RendererBridge):
    async def connect(self, node_id: str, label: str) -> None:
        return

    async def set_mapping(self, mapping_config: dict[str, Any]) -> None:
        return

    async def load_show(self, show_id: str, payload: dict[str, Any]) -> None:
        return

    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None:
        return

    async def pause(self) -> None:
        return

    async def seek(self, position_ms: int) -> None:
        return

    async def stop(self) -> None:
        return

    async def update_layers(self, layers: list[dict[str, Any]]) -> None:
        return

    async def hot_swap(self, layer_id: str, payload: dict[str, Any]) -> None:
        return

    async def ping(self) -> None:
        return

    async def tick(self, snapshot: dict[str, Any]) -> None:
        return

    async def close(self) -> None:
        return


class MockUnityBridge(RendererBridge):
    def __init__(self) -> None:
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._printer_task: asyncio.Task[None] | None = None

    async def connect(self, node_id: str, label: str) -> None:
        self._printer_task = asyncio.create_task(self._printer())
        await self._emit({"event": "connect", "node_id": node_id, "label": label})

    async def set_mapping(self, mapping_config: dict[str, Any]) -> None:
        await self._emit({"event": "set_mapping", "mapping": mapping_config})

    async def load_show(self, show_id: str, payload: dict[str, Any]) -> None:
        await self._emit({"event": "load_show", "show_id": show_id, "payload": payload})

    async def play_at(self, show_id: str, target_time_ms: int | None, payload: dict[str, Any]) -> None:
        await self._emit(
            {
                "event": "play_at",
                "show_id": show_id,
                "target_time_ms": target_time_ms,
                "payload": payload,
            }
        )

    async def pause(self) -> None:
        await self._emit({"event": "pause"})

    async def seek(self, position_ms: int) -> None:
        await self._emit({"event": "seek", "position_ms": position_ms})

    async def stop(self) -> None:
        await self._emit({"event": "stop"})

    async def update_layers(self, layers: list[dict[str, Any]]) -> None:
        await self._emit({"event": "update_layers", "layers": layers})

    async def hot_swap(self, layer_id: str, payload: dict[str, Any]) -> None:
        await self._emit({"event": "hot_swap", "layer_id": layer_id, "payload": payload})

    async def ping(self) -> None:
        await self._emit({"event": "ping"})

    async def tick(self, snapshot: dict[str, Any]) -> None:
        # Keep console noise low; only emit periodic high-level status snapshots.
        if snapshot.get("position_ms", 0) % 5000 < 250:
            await self._emit({"event": "tick", "status": snapshot.get("status"), "pos": snapshot.get("position_ms")})

    async def close(self) -> None:
        if self._printer_task is not None:
            self._printer_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._printer_task

    async def _emit(self, payload: dict[str, Any]) -> None:
        await self._queue.put(json.dumps(payload))

    async def _printer(self) -> None:
        while True:
            line = await self._queue.get()
            print(f"[unity-bridge] {line}")
