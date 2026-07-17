"""
util/SoftwareManager.py — Base class for all CrewAI crews.

Outline:
  load_project_env()          called at import time; loads workspace + project .env
  build_optional_tools()      opt-in extra CrewAI tools gated by env flag
                              (default: empty list — zero behavioral change)
  SoftwareManagerCrew (NOT decorated with @CrewBase — subclasses do that):
    agents / tasks            list attributes subclasses populate
    llm = build_llm()         shared LLM built once at class-definition time
    @agent SoftwareManager    shared agent using agents_config["SoftwareManager"]
    @before_kickoff / @after_kickoff  no-op hooks (overridable)
    @crew crew()              returns Crew(agents, tasks, Process.sequential)
"""
import os
from pathlib import Path
from crewai import Agent, Crew, Process, Task
from crewai.project import agent, crew, before_kickoff, after_kickoff
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from util.llm_config import build_llm, load_project_env

load_project_env()


def build_optional_tools() -> list:
    """Return optional CrewAI tools based on environment flags.

    Default: returns ``[]`` so crews behave exactly like the parent
    SoftwareManager agent. Set ``ENABLE_WEBSITE_SEARCH_TOOL=1`` to attach
    the CrewAI ``WebsiteSearchTool`` — note that tool requires an embedding
    provider to be configured and may fail at runtime if not.
    """
    tools = []
    if os.getenv("ENABLE_WEBSITE_SEARCH_TOOL", "").lower() in ("1", "true", "yes"):
        try:
            from crewai_tools import WebsiteSearchTool
            tools.append(WebsiteSearchTool())
        except Exception:
            # Swallow — the opt-in tool must never block crew construction.
            pass
    return tools

class SoftwareManagerCrew:
    """Base class that provides shared agents and kickoff hooks.
    This class MUST NOT be decorated with @CrewBase."""
    
    # NOT registered automatically — only type hints
    _CONFIG_ROOT = Path(__file__).resolve().parents[1] / "config"
    agents_config = str(_CONFIG_ROOT / "agent" / "agents.yaml")
    tasks_config = str(_CONFIG_ROOT / "task" / "tasks.yaml")
    agents: List[BaseAgent]
    tasks: List[Task]
    llm = build_llm()
    # Shared Agent ---------------------------------------------------
    @agent
    def SoftwareManager(self) -> Agent:
        return Agent(
            config=self.agents_config["SoftwareManager"],
            llm = self.llm,                     # ⭐ 关键
            verbose=True,
            use_agent_data=False
        )

    # Shared lifecycle hooks ----------------------------------------
    @before_kickoff
    def before_kickoff_function(self, inputs):
        return inputs

    @after_kickoff
    def after_kickoff_function(self, result):
        return result

    @crew
    def crew(self) -> Crew:
        """Creates the LatestAiDevelopment crew"""
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
