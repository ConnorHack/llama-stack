# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the terms described in the LICENSE file in
# the root directory of this source tree.

from datetime import datetime
from enum import Enum
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Protocol,
    runtime_checkable,
    Union,
)

from llama_models.schema_utils import json_schema_type, register_schema, webmethod
from pydantic import BaseModel, Field
from typing_extensions import Annotated

# Add this constant near the top of the file, after the imports
DEFAULT_TTL_DAYS = 7


@json_schema_type
class SpanStatus(Enum):
    OK = "ok"
    ERROR = "error"


@json_schema_type
class Span(BaseModel):
    span_id: str
    trace_id: str
    parent_span_id: Optional[str] = None
    name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    attributes: Optional[Dict[str, Any]] = Field(default_factory=dict)

    def set_attribute(self, key: str, value: Any):
        if self.attributes is None:
            self.attributes = {}
        self.attributes[key] = value


@json_schema_type
class Trace(BaseModel):
    trace_id: str
    root_span_id: str
    start_time: datetime
    end_time: Optional[datetime] = None


@json_schema_type
class EventType(Enum):
    UNSTRUCTURED_LOG = "unstructured_log"
    STRUCTURED_LOG = "structured_log"
    METRIC = "metric"


@json_schema_type
class LogSeverity(Enum):
    VERBOSE = "verbose"
    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


class EventCommon(BaseModel):
    trace_id: str
    span_id: str
    timestamp: datetime
    attributes: Optional[Dict[str, Any]] = Field(default_factory=dict)


@json_schema_type
class UnstructuredLogEvent(EventCommon):
    type: Literal[EventType.UNSTRUCTURED_LOG.value] = EventType.UNSTRUCTURED_LOG.value
    message: str
    severity: LogSeverity


@json_schema_type
class MetricEvent(EventCommon):
    type: Literal[EventType.METRIC.value] = EventType.METRIC.value
    metric: str  # this would be an enum
    value: Union[int, float]
    unit: str


@json_schema_type
class StructuredLogType(Enum):
    SPAN_START = "span_start"
    SPAN_END = "span_end"


@json_schema_type
class SpanStartPayload(BaseModel):
    type: Literal[StructuredLogType.SPAN_START.value] = (
        StructuredLogType.SPAN_START.value
    )
    name: str
    parent_span_id: Optional[str] = None


@json_schema_type
class SpanEndPayload(BaseModel):
    type: Literal[StructuredLogType.SPAN_END.value] = StructuredLogType.SPAN_END.value
    status: SpanStatus


StructuredLogPayload = register_schema(
    Annotated[
        Union[
            SpanStartPayload,
            SpanEndPayload,
        ],
        Field(discriminator="type"),
    ],
    name="StructuredLogPayload",
)


@json_schema_type
class StructuredLogEvent(EventCommon):
    type: Literal[EventType.STRUCTURED_LOG.value] = EventType.STRUCTURED_LOG.value
    payload: StructuredLogPayload


Event = register_schema(
    Annotated[
        Union[
            UnstructuredLogEvent,
            MetricEvent,
            StructuredLogEvent,
        ],
        Field(discriminator="type"),
    ],
    name="Event",
)


@json_schema_type
class EvalTrace(BaseModel):
    session_id: str
    step: str
    input: str
    output: str
    expected_output: str


@json_schema_type
class SpanWithStatus(Span):
    status: Optional[SpanStatus] = None


@json_schema_type
class QueryConditionOp(Enum):
    EQ = "eq"
    NE = "ne"
    GT = "gt"
    LT = "lt"


@json_schema_type
class QueryCondition(BaseModel):
    key: str
    op: QueryConditionOp
    value: Any


class QueryTracesResponse(BaseModel):
    data: List[Trace]


class QuerySpansResponse(BaseModel):
    data: List[Span]


class QuerySpanTreeResponse(BaseModel):
    data: Dict[str, SpanWithStatus]


@runtime_checkable
class Telemetry(Protocol):
    @webmethod(route="/telemetry/events", method="POST")
    async def log_event(
        self, event: Event, ttl_seconds: int = DEFAULT_TTL_DAYS * 86400
    ) -> None: ...

    @webmethod(route="/telemetry/traces", method="GET")
    async def query_traces(
        self,
        attribute_filters: Optional[List[QueryCondition]] = None,
        limit: Optional[int] = 100,
        offset: Optional[int] = 0,
        order_by: Optional[List[str]] = None,
    ) -> QueryTracesResponse: ...

    @webmethod(route="/telemetry/traces/{trace_id}", method="GET")
    async def get_trace(self, trace_id: str) -> Trace: ...

    @webmethod(route="/telemetry/traces/{trace_id}/spans/{span_id}", method="GET")
    async def get_span(self, trace_id: str, span_id: str) -> Span: ...

    @webmethod(route="/telemetry/spans/{span_id}/tree", method="GET")
    async def get_span_tree(
        self,
        span_id: str,
        attributes_to_return: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
    ) -> QuerySpanTreeResponse: ...

    @webmethod(route="/telemetry/spans", method="GET")
    async def query_spans(
        self,
        attribute_filters: List[QueryCondition],
        attributes_to_return: List[str],
        max_depth: Optional[int] = None,
    ) -> QuerySpansResponse: ...

    @webmethod(route="/telemetry/spans/export", method="POST")
    async def save_spans_to_dataset(
        self,
        attribute_filters: List[QueryCondition],
        attributes_to_save: List[str],
        dataset_id: str,
        max_depth: Optional[int] = None,
    ) -> None: ...
