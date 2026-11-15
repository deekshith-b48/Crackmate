"""Stream a long job to the browser as NDJSON: step events, then one result or error."""
import asyncio
import json
import queue
import threading

from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from api.errors import describe


def stream_events(fn, heartbeat=15):
    """Run fn(emit) on a worker thread. Whatever fn emits becomes one NDJSON line; failures become a friendly error event."""
    events = queue.Queue()

    def work():
        try:
            fn(lambda event: events.put(jsonable_encoder(event)))
        except Exception as exc:  # noqa: BLE001 - every failure must reach the browser as a friendly event
            events.put({"type": "error", "message": describe(exc)[1]})
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    async def body():
        while True:
            try:
                event = await asyncio.to_thread(events.get, True, heartbeat)
            except queue.Empty:
                yield b'{"type":"ping"}\n'  # keeps proxies from closing a quiet connection
                continue
            if event is None:
                return
            yield (json.dumps(event, ensure_ascii=False) + "\n").encode()

    return StreamingResponse(body(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


def stream_job(fn, heartbeat=15):
    """Run fn(progress) and stream its progress as step events, then one result (or error) event."""
    def run(emit):
        emit({"type": "result", "data": fn(lambda text: emit({"type": "step", "text": str(text)}))})
    return stream_events(run, heartbeat)
