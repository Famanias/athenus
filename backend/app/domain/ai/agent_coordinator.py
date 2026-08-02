from typing import Dict, List, Any
from app.domain.ai.agent_protocol import BaseAgent, TaskContext, AgentInput, AgentOutput
from app.domain.ai.agents.specialized_agents import PlannerAgent, RetrieverAgent, CitationValidatorAgent

class AgentCoordinator:
    """Orchestrates multi-agent execution workflows."""
    
    def __init__(self) -> None:
        self._agents: Dict[str, BaseAgent] = {
            "planner": PlannerAgent(),
            "retriever": RetrieverAgent(),
            "validator": CitationValidatorAgent()
        }

    def list_agents(self) -> List[str]:
        return list(self._agents.keys())

    async def coordinate_task(self, input_data: AgentInput) -> Dict[str, AgentOutput]:
        results: Dict[str, AgentOutput] = {}
        for agent_id, agent in self._agents.items():
            if agent.is_applicable(input_data.context):
                out = await agent.execute(input_data)
                results[agent_id] = out
        return results
