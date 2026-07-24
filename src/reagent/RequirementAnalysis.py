# src/reagent/RequirementAnalysis.py — Stage 4 crews (Analysis).
#
# Outline:
#   RequirementsAnalysisDevCrew(SoftwareManagerCrew)  marker subclass
#   Crews:
#     STDCrew               state_transition_diagram.md (Mermaid)
#     DataFlowDiagramCrew   data_flow_diagram.md (Mermaid)
#     DialogMapCrew         dialog_map.md (Mermaid)
#     ERDCrew               entity_relationship_diagram.md (Mermaid)
#     DataDictionaryCrew    data_dictionary.md
#     FRCrew                functional_requirements.md
#   Runner classes:
#     datadictionaryRun, ERDRun, DataFlowDiagramRun,
#     FunctionRequirementRun, DialogMaprun
#   All use run_with_retry; post_process validates output length.
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task, before_kickoff, after_kickoff
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from util.SoftwareManager import SoftwareManagerCrew
from util import *
from util.util import get_store_path
class RequirementsAnalysisDevCrew(SoftwareManagerCrew):
    pass
   
@CrewBase
class STDCrew(RequirementsAnalysisDevCrew):
    @task
    def state_transition_diagram_task(self) -> Task:
        return Task(
            config=self.tasks_config["state_transition_diagram_task"],
                output_file=f"{get_store_path()}/state_transition_diagram.md",
                agent = self.SoftwareManager()
            )
    
@CrewBase
class DataFlowDiagramCrew(RequirementsAnalysisDevCrew):
    @task
    def data_flow_diagram_task(self) -> Task:
        return Task(
            config=self.tasks_config["data_flow_diagram_draft_task"],
                output_file=f"{get_store_path()}/data_flow_diagram.md",
                agent = self.SoftwareManager()
            )
    
@CrewBase
class DialogMapCrew(RequirementsAnalysisDevCrew):
    @task
    def DialogMap_task(self) -> Task:
        return Task(
            config=self.tasks_config["dialog_map_draft_task"],
                output_file=f"{get_store_path()}/dialog_map.md",
                agent = self.SoftwareManager()
            )
    
@CrewBase
class DataDictionaryCrew(RequirementsAnalysisDevCrew):
    @task
    def DataDictionary_task(self) -> Task:
        return Task(
            config=self.tasks_config["data_dictionary_draft_task"],
                output_file=f"{get_store_path()}/data_dictionary.md",
                agent = self.SoftwareManager()
            )
    

    
@CrewBase
class ERDCrew(RequirementsAnalysisDevCrew):
    @task
    def erd_task(self) -> Task:
        return Task(
            config=self.tasks_config["erd_task"],
            output_file=f"{get_store_path()}/entity_relationship_diagram.md",
            agent = self.SoftwareManager()
        )
    
@CrewBase
class FRCrew(RequirementsAnalysisDevCrew):
    @task
    def fr_task(self) -> Task:
        return Task(
            config=self.tasks_config["fr_task"],
            output_file=f"{get_store_path()}/functional_requirements.md",
            agent = self.SoftwareManager()
        )
    
class FunctionRequirementRun():
    def __init__(self, project_name,Description):
        self.project_name = project_name
        self.Description = Description
        
    def functional_requirements_post_process(self):
        functional_requirements = get_functional_requirements()
        if len(functional_requirements) < 100:
            raise TypeError("Expected functional_requirements too short.") 

    def run(self):
        fn_inputs = {
        'reference': get_reference(['use_case']),
        'project_name': self.project_name,
        'Description': self.Description
    }
        run_with_retry(FRCrew, 
                   fn_inputs, 
                   name="FRCrew",
                    post_process_callable=self.functional_requirements_post_process)
        
class DataFlowDiagramRun():
    def __init__(self, project_name,Description):
        self.project_name = project_name
        self.Description = Description

    def data_flow_diagram_post_process(self):
        data_flow_diagram = get_data_flow_diagram()
        if len(data_flow_diagram) < 100:
            raise TypeError("Expected data_flow_diagram too short.") 
        
    def run(self):
        DFD_inputs = {
        'project_name': self.project_name,
        'reference': get_reference(['context_diagram', 'use_case']),
        'Description': self.Description
    }
        run_with_retry(DataFlowDiagramCrew, 
                   DFD_inputs, 
                   name="DataFlowDiagramCrew",
                   post_process_callable=self.data_flow_diagram_post_process)
        
class ERDRun():
    def __init__(self, project_name,Description):
        self.project_name = project_name
        self.Description = Description
        
    def ERD_post_process(self):
        ERD = get_ERD()
        if len(ERD) < 100:
            raise TypeError("Expected ERD too short.") 
        
    def run(self):
        ERD_inputs = {
        'reference': get_reference(['context_diagram', 'data_flow_diagram']),
        'project_name': self.project_name,
        'Description': self.Description
    }
        run_with_retry(ERDCrew, 
                   ERD_inputs, 
                   name="ERDCrew",
                    post_process_callable=self.ERD_post_process)
        
class datadictionaryRun():
    def __init__(self, project_name,Description):
        self.project_name = project_name
        self.Description = Description

    def data_dictionary_post_process(self):
        data_dictionary = get_data_dictionary()
        if len(data_dictionary) < 100:
            raise TypeError("Expected data_dictionary too short.") 
    
    def run(self):
        DD_inputs = {
        'reference': get_reference(['ERD']),
        'project_name': self.project_name,
        'Description': self.Description
    }
        run_with_retry(DataDictionaryCrew, 
                   DD_inputs, 
                   name="DataDictionaryCrew",
                    post_process_callable=self.data_dictionary_post_process)

class DialogMaprun():
    def __init__(self, project_name,Description):
        self.project_name = project_name
        self.Description = Description
        self.dependencies = ['use_case']

    def dialog_map_post_process(self):
        dialog_map = get_dialog_map()
        if len(dialog_map) < 100:
            raise TypeError("Expected dialog_map too short.") 

    def run(self):
        DM_inputs = {
            'reference' : get_reference(self.dependencies),
            'project_name': self.project_name,
            'Description': self.Description
        }
        run_with_retry(DialogMapCrew, 
                   DM_inputs, 
                   name="DialogMapCrew",
                    post_process_callable=self.dialog_map_post_process)
