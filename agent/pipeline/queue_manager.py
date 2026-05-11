from __future__ import annotations
import os
import json
import time
from typing import Optional, Dict, Any
from redis import Redis
from redis.exceptions import RedisError
from dotenv import load_dotenv
from .schema import PipelineMessage

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


class QueueManager:
    QUEUE_MEMPOOL_RAW = "flashix:queue:mempool_raw"
    QUEUE_INFERENCE_REQUESTS = "flashix:queue:inference_requests"
    QUEUE_AGENT_DECISIONS = "flashix:queue:agent_decisions"
    QUEUE_EXECUTION_REQUESTS = "flashix:queue:execution_requests"
    QUEUE_SETTLEMENT_UPDATES = "flashix:queue:settlement_updates"
    QUEUE_DLQ = "flashix:queue:dead_letter"

    def __init__(self, redis_url: str = None):
        self.redis_url = redis_url or REDIS_URL
        self._client = Redis.from_url(self.redis_url, decode_responses=True)

    def push(self, queue: str, message: PipelineMessage, priority: int = 0) -> None:
        try:
            # If message is dataclass-like with to_dict, include original queue metadata
            if hasattr(message, 'to_dict'):
                try:
                    meta = message.to_dict()
                except Exception:
                    meta = {}
                meta.setdefault('original_queue', queue)
                payload = json.dumps(meta)
            else:
                payload = message.to_json() if hasattr(message, 'to_json') else json.dumps(message)
            # Use ZADD; lower score == higher priority if calling code uses negative scores
            # Retry a small number of times on transient Redis errors
            attempts = 0
            while True:
                try:
                    self._client.zadd(queue, {payload: float(priority)})
                    break
                except RedisError as e:
                    attempts += 1
                    if attempts >= 3:
                        raise
                    time.sleep(0.1 * attempts)
        except RedisError as e:
            raise

    def pop(self, queue: str, timeout_seconds: int = 1) -> Optional[PipelineMessage]:
        try:
            res = self._client.bzpopmin(queue, timeout=timeout_seconds)
            if not res:
                return None
            # bzpopmin returns (key, member, score)
            _, member, _ = res
            data = json.loads(member)
            # Attempt to map to PipelineMessage or appropriate subclass
            return PipelineMessage.from_dict(data)
        except RedisError:
            return None

    def move_to_dlq(self, message: PipelineMessage, failure_reason: str) -> None:
        try:
            meta = message.to_dict()
            meta["failure_reason"] = failure_reason
            meta["failed_at_ms"] = int(__import__("time").time() * 1000)
            # include/increment retry count
            meta['retries'] = int(meta.get('retries', 0)) + 1
            self._client.zadd(self.QUEUE_DLQ, {json.dumps(meta): float(meta.get("failed_at_ms"))})
        except RedisError:
            pass

    def process_dlq(self, max_retries: int = 3, backoff_base_seconds: int = 5) -> None:
        """Scan DLQ and requeue eligible messages with exponential backoff.

        Messages with retries >= max_retries are left in DLQ for manual inspection.
        """
        try:
            items = self._client.zrange(self.QUEUE_DLQ, 0, -1, withscores=False)
            now_ms = int(time.time() * 1000)
            for raw in items:
                try:
                    meta = json.loads(raw)
                except Exception:
                    # malformed entry; skip
                    continue
                retries = int(meta.get('retries', 0))
                failed_at = int(meta.get('failed_at_ms', now_ms))
                # calculate backoff: base * 2^(retries-1)
                backoff_seconds = backoff_base_seconds * (2 ** max(0, retries - 1))
                if retries < max_retries and (now_ms - failed_at) >= backoff_seconds * 1000:
                    # requeue to original target if present, otherwise to inference requests
                    target = meta.get('original_queue') or self.QUEUE_INFERENCE_REQUESTS
                    # remove from DLQ
                    try:
                        self._client.zrem(self.QUEUE_DLQ, raw)
                    except Exception:
                        pass
                    # increment retries and update failed_at
                    meta['retries'] = retries + 1
                    meta['failed_at_ms'] = now_ms
                    # push back to target
                    payload = json.dumps(meta)
                    try:
                        self._client.zadd(target, {payload: float(now_ms)})
                    except Exception:
                        # if requeue fails, put back into DLQ
                        self._client.zadd(self.QUEUE_DLQ, {json.dumps(meta): float(now_ms)})
                else:
                    # keep in DLQ
                    continue
        except RedisError:
            return

    def get_queue_depths(self) -> Dict[str, int]:
        qnames = [
            self.QUEUE_MEMPOOL_RAW,
            self.QUEUE_INFERENCE_REQUESTS,
            self.QUEUE_AGENT_DECISIONS,
            self.QUEUE_EXECUTION_REQUESTS,
            self.QUEUE_SETTLEMENT_UPDATES,
            self.QUEUE_DLQ,
        ]
        depths = {}
        for q in qnames:
            try:
                depths[q] = self._client.zcard(q)
            except RedisError:
                depths[q] = -1
        return depths
