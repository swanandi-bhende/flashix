from __future__ import annotations
from dataclasses import dataclass, field, asdict, fields
from decimal import Decimal
from typing import Optional, Literal, Dict, Any
import time
import uuid
import json

PipelineStage = Literal[
    "MEMPOOL_DETECTED",
    "OPPORTUNITY_FILTERED",
    "INFERENCE_REQUESTED",
    "INFERENCE_COMPLETED",
    "AGENT_DECISION_REQUESTED",
    "AGENT_DECISION_COMPLETED",
    "EXECUTION_REQUESTED",
    "EXECUTION_CONFIRMED",
    "SETTLEMENT_COMPLETED",
    "OPPORTUNITY_EXPIRED",
    "OPPORTUNITY_REJECTED",
]


def now_ms() -> int:
    return int(time.time() * 1000)


def _serialize(obj: Any):
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, uuid.UUID):
        return str(obj)
    return obj


@dataclass
class PipelineMessage:
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = ""
    pipeline_stage: PipelineStage = "MEMPOOL_DETECTED"
    created_at_ms: int = field(default_factory=now_ms)
    hop_count: int = 0
    source_component: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return json.loads(json.dumps(d, default=_serialize))

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=_serialize)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineMessage":
        # Choose subclass based on pipeline_stage if available
        stage = data.get("pipeline_stage")
        mapping = {
            "MEMPOOL_DETECTED": MempoolDetectedMessage,
            "OPPORTUNITY_FILTERED": InferenceRequestMessage,
            "INFERENCE_REQUESTED": InferenceRequestMessage,
            "INFERENCE_COMPLETED": InferenceResponseMessage,
            "AGENT_DECISION_REQUESTED": AgentDecisionMessage,
            "AGENT_DECISION_COMPLETED": AgentDecisionMessage,
            "EXECUTION_REQUESTED": PipelineMessage,
            "EXECUTION_CONFIRMED": ExecutionResultMessage,
            "SETTLEMENT_COMPLETED": PipelineMessage,
            "OPPORTUNITY_EXPIRED": PipelineMessage,
            "OPPORTUNITY_REJECTED": PipelineMessage,
        }

        target = mapping.get(stage, PipelineMessage)

        # filter fields to those present in dataclass to avoid unexpected kwargs
        field_names = {f.name for f in fields(target)}
        filtered = {k: v for k, v in data.items() if k in field_names}
        return target(**filtered)


@dataclass
class OpportunityCandidate:
    id: str
    raw_tx: Dict[str, Any]
    opportunityScore: float
    detected_at_ms: int = field(default_factory=now_ms)


@dataclass
class MempoolDetectedMessage(PipelineMessage):
    raw_opportunity: Any = None


@dataclass
class InferenceInput:
    features: Dict[str, Any]
    expiry_timestamp: int


@dataclass
class InferenceRequestMessage(PipelineMessage):
    inference_input: Any = None
    inference_deadline_ms: int = 0


@dataclass
class InferenceOutput:
    decision: str
    score: float
    expiry_timestamp: int
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class InferenceResponseMessage(PipelineMessage):
    inference_output: Any = None
    inference_latency_ms: float = 0.0
    tee_verified: bool = False


@dataclass
class ReasoningTrace:
    trace_id: str
    steps: Dict[str, Any]


@dataclass
class AgentDecisionMessage(PipelineMessage):
    reasoning_trace: Any = None
    decision: str = ""
    decision_id: str = ""


@dataclass
class ExecutionResult:
    status: str
    tx_hash: Optional[str]
    block_number: Optional[int]
    gas_used: Optional[int]
    explorer_link: Optional[str]
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResultMessage(PipelineMessage):
    execution_result: Any = None
    realized_profit_usdc: Optional[Decimal] = None


@dataclass
class ExecutionRequestMessage(PipelineMessage):
    execution_request: Any = None


@dataclass
class CorrelationRecord:
    correlation_id: str
    current_stage: PipelineStage
    stage_timestamps: Dict[str, int] = field(default_factory=dict)
    total_latency_ms: Optional[int] = None
    outcome: Optional[str] = None
    created_at: int = field(default_factory=now_ms)

    def to_dict(self) -> Dict[str, Any]:
        return json.loads(json.dumps(asdict(self), default=_serialize))
