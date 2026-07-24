# src/reagent/RequirementSpecification.py — Stage 6 crews (SRS Generation).
#
# Outline:
#   RequirementsSpecificationDevCrew(SoftwareManagerCrew)
#       overrides SoftwareManager agent (drops verbose=True)
#   SRSev            writes software_requirements_specification_chapter.md
#                    (one chapter per call, driven by main.py chapter loop)
#   SRSplaningCrew   writes srs_planning.md (per-chapter writing plan)
from util.SoftwareManager import SoftwareManagerCrew
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task, before_kickoff, after_kickoff
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from util.util import get_store_path
import os

class RequirementsSpecificationDevCrew(SoftwareManagerCrew):
    @agent
    def SoftwareManager(self) -> Agent:
        return Agent(
            config=self.agents_config["SoftwareManager"], # Gets injected by subclasses
            use_agent_data=False,
            llm = self.llm
            # memory = True,
        )

@CrewBase
class SRSev(RequirementsSpecificationDevCrew):
    @task
    def software_requirements_specification_chapter(self) -> Task:
        return Task(
            config=self.tasks_config["SRS_draft_task"],
            output_file=f"{get_store_path()}/software_requirements_specification_chapter.md",
            agent = self.SoftwareManager()
        )
   
@CrewBase
class SRSplaningCrew(RequirementsSpecificationDevCrew):
    @task
    def srs_planning_task(self) -> Task:
        return Task(
            config=self.tasks_config["SRS_planning_task"],
            output_file=f"{get_store_path()}/srs_planning.md",
            agent = self.SoftwareManager()
        )

    
