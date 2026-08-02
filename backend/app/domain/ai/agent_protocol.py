from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol

@dataclass
class TaskContext:
    workspace_id: str
    user_id: str
    media_id: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentInput:
    task_type: str
    query_text: str
    context: TaskContext
    payload: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AgentOutput:
    agent_name: str
    success: bool
    data: Dict[str, Any]
    error_message: str = ""

class BaseAgent(Protocol):
    agent_name: str

    def is_applicable(self, task: TaskContext) -> bool: ...
    def required_tools(self) -> List[str]: ...
    async def execute(self, input_data: AgentInput) -> AgentOutput: ...
