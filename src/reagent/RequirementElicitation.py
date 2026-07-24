# src/reagent/RequirementElicitation.py — Stage 3 crews (Elicitation).
#
# Outline:
#   RequirementsElicitationDevCrew(SoftwareManagerCrew)  marker subclass
#   UsageScenarioCrew   writes usage_scenario.md
#   UserCaseCrew        writes use_case.md (validated as JSON list of UserCase)
#   NFRCrew             writes non_functional_requirements.md
#   UserCaseRun         wrapper with UC_post_process (validates format →
#                       pickles UseCase.pkl list)
#   NFRRun              wrapper with length sanity check post_process
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task, before_kickoff, after_kickoff
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from util.SoftwareManager import SoftwareManagerCrew
from util.util import get_store_path
from util import *
class RequirementsElicitationDevCrew(SoftwareManagerCrew):
    pass
    
@CrewBase
class UsageScenarioCrew(RequirementsElicitationDevCrew):
    @task
    def usage_scenario_task(self) -> Task:
        return Task(
            config=self.tasks_config["usage_scenario_task"],
            output_file=f"{get_store_path()}/usage_scenario.md",
            agent = self.SoftwareManager()
        )

@CrewBase
class UserCaseCrew(RequirementsElicitationDevCrew):
    @task
    def user_case_task(self) -> Task:
        return Task(
            config=self.tasks_config["use_case_draft_task"],
            output_file=f"{get_store_path()}/use_case.md",
            agent = self.SoftwareManager()
        )
        

@CrewBase
class NFRCrew(RequirementsElicitationDevCrew):
    @task
    def nfr_task(self) -> Task:
        return Task(
            config=self.tasks_config["nfr_task"],
            output_file=f"{get_store_path()}/non_functional_requirements.md",
            agent = self.SoftwareManager()
        )
    
class UserCaseRun():
    def __init__(self, project_name, Description):
        self.project_name = project_name
        self.Description = Description

    def UC_post_process(self):
        UserCaseList = json.loads(
            read_markdown(f"{get_store_path()}/use_case.md")
        )
        is_valid, message = validate_use_case_format(UserCaseList)
        if not is_valid:
            raise ValueError(f"Use case format error: {message}")
        UCL = [UserCase(uc) for uc in UserCaseList]
        with open(f"{get_store_path()}/UseCase.pkl", "wb") as f:
            pickle.dump(UCL, f)
    
    def run(self,feedback,execute):
        UC_inputs = {
                'reference': get_reference(['context_diagram', 'event_list', 'user_introduction']),
                'project_name': self.project_name,
                'Description' : self.Description, 
                'feedback': feedback + execute.get('use_case',''),
                'original' : '' if 'all' in execute else get_user_case()
            }
        run_with_retry(UserCaseCrew, 
                        UC_inputs, 
                        name="UserCaseCrew",
                        post_process_callable=self.UC_post_process,)
        
class NFRRun():
    def __init__(self, project_name, Description):
        self.project_name = project_name
        self.Description = Description

    def NFR_post_process(self):
        NFR = get_non_functional_requirements()
        if len(NFR) < 100:
            raise TypeError("Expected NFR too short.")
    
    def run(self,feedback,execute):
        NFR_inputs = {
                'reference': get_reference(['survey']),
                'project_name': self.project_name,
                "Description" : self.Description, 
                'feedback': feedback + execute.get('non_functional_requirements',''),
                'original' : '' if 'all' in execute else get_non_functional_requirements()
            }
        run_with_retry(NFRCrew, 
                    NFR_inputs, 
                    name="NFRCrew",
                    post_process_callable=self.NFR_post_process)
