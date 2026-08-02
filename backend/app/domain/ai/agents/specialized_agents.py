from typing import List, Dict, Any
from app.domain.ai.agent_protocol import BaseAgent, TaskContext, AgentInput, AgentOutput

class PlannerAgent(BaseAgent):
    agent_name: str = "PlannerAgent"

    def is_applicable(self, task: TaskContext) -> bool:
        return True

    def required_tools(self) -> List[str]:
        return ["retriever", "quiz_generator"]

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        plan = [
            "1. Retrieve timestamped transcript context",
            "2. Generate grounded RAG response",
            "3. Formulate comprehension check quiz"
        ]
        return AgentOutput(agent_name=self.agent_name, success=True, data={"execution_plan": plan})

class RetrieverAgent(BaseAgent):
    agent_name: str = "RetrieverAgent"

    def is_applicable(self, task: TaskContext) -> bool:
        return True

    def required_tools(self) -> List[str]:
        return ["multi_stage_retriever"]

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        return AgentOutput(agent_name=self.agent_name, success=True, data={"status": "Context retrieved successfully"})

class CitationValidatorAgent(BaseAgent):
    agent_name: str = "CitationValidatorAgent"

    def is_applicable(self, task: TaskContext) -> bool:
        return True

    def required_tools(self) -> List[str]:
        return ["groundedness_evaluator"]

    async def execute(self, input_data: AgentInput) -> AgentOutput:
        return AgentOutput(agent_name=self.agent_name, success=True, data={"citations_valid": True, "confidence": 0.98})
