# src/reagent/MetaAnalysis.py — Stage 1 crews (Template meta-analysis).
#
# Outline:
#   MetaAnalysisDevCrew(SoftwareManagerCrew)  marker subclass
#   ExtractDocumentCrew     document_skeleton.md  (JSON template structure)
#   DocContentCrew          doc_content.md        (per-chapter content plan)
#   ChapterDependenceCrew   chapter_dependence.md (chapter deps dict)
#   ArtifactPlanningCrew    artifact_planning.md  (chapter→artifacts map)
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task, before_kickoff, after_kickoff
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from util.SoftwareManager import SoftwareManagerCrew
from util.util import get_store_path
from pydantic import BaseModel
class MetaAnalysisDevCrew(SoftwareManagerCrew):
    pass

@CrewBase
class ExtractDocumentCrew(MetaAnalysisDevCrew):
    @task
    def extract_document_skeleton_task(self) -> Task:
        return Task(
            config=self.tasks_config["extract_document_skeleton_task"],
            output_file=f"{get_store_path()}/document_skeleton.md",
            agent = self.SoftwareManager()
        )
        
@CrewBase
class ArtifactPlanningCrew(MetaAnalysisDevCrew):
    @task
    def artifact_planning_task(self) -> Task:
        return Task(
            config=self.tasks_config["artifact_planning_task"],
            output_file=f"{get_store_path()}/artifact_planning.md",
            agent = self.SoftwareManager()
        )
        
@CrewBase
class DocContentCrew(MetaAnalysisDevCrew):
    @task
    def doc_content_task(self) -> Task:
        return Task(
            config=self.tasks_config["doc_content_task"],
            output_file=f"{get_store_path()}/doc_content.md",
            agent = self.SoftwareManager()
        )



@CrewBase
class ChapterDependenceCrew(MetaAnalysisDevCrew):
    @task
    def chapter_dependence_task(self) -> Task:
        return Task(
            config=self.tasks_config["chapter_dependence_task"],
            output_file=f"{get_store_path()}/chapter_dependence.md",
            agent = self.SoftwareManager()
        )
