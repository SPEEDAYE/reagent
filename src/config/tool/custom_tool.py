"""Tool contract: example CrewAI custom tool.

Purpose:
    Demonstrates the shape of a CrewAI ``BaseTool`` implementation.
Call boundary:
    This is a placeholder only and is not wired into the production crews.
Inputs:
    ``argument``: free-form string supplied by an agent.
Outputs:
    A short string result.
Permissions:
    No filesystem, network, shell, database, or credential access.
Failure handling:
    Current implementation is deterministic and should not raise for valid
    string input.
Safety:
    Do not add side effects here without documenting the new permission and
    failure model in this contract block.
"""

from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field


class MyCustomToolInput(BaseModel):
    """Input schema for MyCustomTool."""
    argument: str = Field(..., description="Description of the argument.")

class MyCustomTool(BaseTool):
    name: str = "Name of my tool"
    description: str = (
        "Clear description for what this tool is useful for, your agent will need this information to use it."
    )
    args_schema: Type[BaseModel] = MyCustomToolInput

    def _run(self, argument: str) -> str:
        # Implementation goes here
        return "this is an example of a tool output, ignore it and move along."
