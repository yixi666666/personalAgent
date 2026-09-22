import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator


logger = logging.getLogger(__name__)

DONE = object()


@dataclass
class _Stream:
    session_id: str
    stream_id: str
    user_id: str
    events: list[dict] = field(default_factory=list)
    queues: list[asyncio.Queue] = field(default_factory=list)
    done: bool = False
    finished_at: float | None = None
    task: asyncio.Task | None = None

    def publish(self, event: dict) -> None:
        self.events.append(event)
        for queue in self.queues:
            queue.put_nowait(event)

    def finish(self) -> None:
        if self.done:
            return
        self.done = True
        self.finished_at = time.monotonic()
        for queue in self.queues:
            queue.put_nowait(DONE)


class StreamBus:
    """单进程内的对话流事件总线。"""

    def __init__(self, ttl_seconds: int = 600) -> None:
        self._streams: dict[str, _Stream] = {}
        self._ttl_seconds = ttl_seconds

    def _cleanup(self) -> None:
        now = time.monotonic()
        expired = [
            stream_id
            for stream_id, stream in self._streams.items()
            if stream.done
            and stream.finished_at is not None
            and now - stream.finished_at >= self._ttl_seconds
        ]
        for stream_id in expired:
            del self._streams[stream_id]

    def start_stream(
        self,
        session_id: str,
        stream_id: str,
        user_id: str,
        pipeline: AsyncGenerator[dict, None],
    ) -> _Stream:
        self._cleanup()
        stream = _Stream(session_id=session_id, stream_id=stream_id, user_id=user_id)
        self._streams[stream_id] = stream
        stream.task = asyncio.create_task(
            self._run(stream, pipeline),
            name=f"chat-stream-{stream_id}",
        )
        return stream

    async def _run(
        self,
        stream: _Stream,
        pipeline: AsyncGenerator[dict, None],
    ) -> None:
        produced_finish = False
        try:
            async for event in pipeline:
                if event.get("type") == "finish":
                    produced_finish = True
                stream.publish(event)
        except asyncio.CancelledError:
            stream.publish({"type": "error", "error": "处理被中断（服务关闭）"})
            stream.finish()
            raise
        except Exception as exc:
            logger.exception("对话后台处理失败 stream_id=%s", stream.stream_id)
            stream.publish({"type": "error", "error": f"处理失败: {exc}"})
            stream.publish({"type": "finish", "finish_reason": "error"})
            stream.finish()
        else:
            if not produced_finish:
                stream.publish({"type": "finish", "finish_reason": "stop"})
            stream.finish()

    def subscribe(self, stream_id: str, user_id: str) -> tuple[list[dict], asyncio.Queue] | None:
        self._cleanup()
        stream = self._streams.get(stream_id)
        if stream is None or stream.user_id != user_id:
            return None

        events = list(stream.events)
        queue: asyncio.Queue[Any] = asyncio.Queue()
        if stream.done:
            queue.put_nowait(DONE)
        else:
            stream.queues.append(queue)
        return events, queue

    def unsubscribe(self, stream_id: str, queue: asyncio.Queue) -> None:
        stream = self._streams.get(stream_id)
        if stream is not None and queue in stream.queues:
            stream.queues.remove(queue)

    def get(self, stream_id: str, user_id: str) -> _Stream | None:
        self._cleanup()
        stream = self._streams.get(stream_id)
        if stream is None or stream.user_id != user_id:
            return None
        return stream

    def active_stream_for_session(self, session_id: str, user_id: str) -> _Stream | None:
        self._cleanup()
        for stream in self._streams.values():
            if stream.session_id == session_id and stream.user_id == user_id and not stream.done:
                return stream
        return None

    async def shutdown(self) -> None:
        tasks = [
            stream.task
            for stream in self._streams.values()
            if stream.task is not None and not stream.task.done()
        ]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


_stream_bus = StreamBus()


def get_stream_bus() -> StreamBus:
    return _stream_bus
