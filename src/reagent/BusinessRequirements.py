# src/reagent/BusinessRequirements.py — Stage 2 crews (BR).
#
# Outline:
#   BusinessRequirementsDevCrew(SoftwareManagerCrew)  shared base (no @CrewBase)
#   Subcrews (@CrewBase-decorated, each with dedicated agents + tasks):
#     SurveyCrew             market/competitive survey
#     ContextDiagramCrew     system context diagram (Mermaid)
#     EventListCrew          external event list
#     UserIntroductionCrew   user personas / roles
#     FeatureTreeCrew        hierarchical feature breakdown
#     BusinessScopeCrew      business boundaries & stakeholders
#     BRDev                  per-chapter BRD writer (called per chapter 1..N)
#     BRDModifyLocateCrew    decides which artifacts to regenerate (JSON list)
#     BRDModifyCrew          regenerates those artifacts with feedback injected
#   Runner classes (surveyRun, ContextDiagramRun, eventlistRun,
#                   UserIntroductionRun, FeatureTreeRun, BusinessScopeRun)
#     thin wrappers with .run(feedback, execute) using run_with_retry.
#
# The shared SoftwareManager agent receives optional CrewAI tools via
# build_optional_tools() (util/SoftwareManager.py) — empty list by default,
# opt-in to WebsiteSearchTool with ENABLE_WEBSITE_SEARCH_TOOL=1.
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task, before_kickoff, after_kickoff
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from util.SoftwareManager import SoftwareManagerCrew, build_optional_tools
from util.util import get_store_path
from util import *
# -------------------------------------------------------------------
# PARENT CLASS — Only defines shared methods (NO @CrewBase)
# -------------------------------------------------------------------
class BusinessRequirementsDevCrew(SoftwareManagerCrew):
    """Base class that provides shared agents and kickoff hooks.
    This class MUST NOT be decorated with @CrewBase."""

    # Shared Agent ---------------------------------------------------
    @agent
    def SoftwareManager(self) -> Agent:
        return Agent(
            config=self.agents_config["SoftwareManager"], # Gets injected by subclasses
            verbose=True,
            llm = self.llm, 
            tools=build_optional_tools(),
        )


# -------------------------------------------------------------------
# CHILD CREWS — These are actual runnable crews
# Each is decorated with @CrewBase
# Each gets its own tasks
# All inherit the same SoftwareManager + hooks
# -------------------------------------------------------------------

@CrewBase
class CompetitiveAnalysisCrew(BusinessRequirementsDevCrew):
    @task
    def competitive_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["competitive_analysis_task"],
            output_file=f"{get_store_path()}/competitive_analysis.md",
            agent = self.SoftwareManager()
        )
        
@CrewBase
class BRDModifyCrew(BusinessRequirementsDevCrew):
    @task
    def competitive_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["BRD_modify_task"],
            output_file=f"{get_store_path()}/BRD_modify.md",
            agent = self.SoftwareManager()
        )
    
@CrewBase
class BRDModifyLocateCrew(BusinessRequirementsDevCrew):
    @task
    def competitive_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config["BRD_modify_locate_task"],
            output_file=f"{get_store_path()}/BRD_modify.md",
            agent = self.SoftwareManager()
        )

@CrewBase
class SurveyCrew(BusinessRequirementsDevCrew):
    @task
    def survey_task(self) -> Task:
        return Task(
            config=self.tasks_config["survey_task"],
            output_file=f"{get_store_path()}/survey.md",
            agent = self.SoftwareManager()
        )
    
@CrewBase
class FeatureTreeDev(BusinessRequirementsDevCrew):
    @task
    def feature_tree_task(self) -> Task:
        return Task(
            config=self.tasks_config["draft_feature_tree_task"],
            output_file=f"{get_store_path()}/feature_tree.md",
            agent = self.SoftwareManager()
        )

@CrewBase
class BRDev(BusinessRequirementsDevCrew):
    @task
    def business_requirements_document_chapter(self) -> Task:
        return Task(
            config=self.tasks_config["business_requirements_document_task"],
            output_file=f"{get_store_path()}/business_requirements_chapter.md",
            agent = self.SoftwareManager()
        )
    
@CrewBase
class UserIntroductionDev(BusinessRequirementsDevCrew):
    @task
    def draft_user_introduction(self) -> Task:
        return Task(
            config=self.tasks_config["user_introduction_draft_task"],
            output_file=f"{get_store_path()}/user_introduction.md",
            agent = self.SoftwareManager()
        )

@CrewBase
class DraftContentDiagramCrew(BusinessRequirementsDevCrew):
    @task
    def draft_context_diagram_task(self) -> Task:
        return Task(
            config=self.tasks_config["draft_context_diagram_task"],
            output_file=f"{get_store_path()}/draft_context_diagram.md",
            agent = self.SoftwareManager()
        )
    
@CrewBase
class DraftEventListCrew(BusinessRequirementsDevCrew):
    @task
    def draft_event_list_task(self) -> Task:
        return Task(
            config=self.tasks_config["draft_event_list_task"],
            output_file=f"{get_store_path()}/draft_event_list.md",
            agent = self.SoftwareManager()
        )
        
@CrewBase
class BusinessScopeDev(BusinessRequirementsDevCrew):
    @task
    def business_scope_task(self) -> Task:
        return Task(
            config=self.tasks_config["business_scope_task"],
            output_file=f"{get_store_path()}/business_scope.md",
            agent = self.SoftwareManager()
        )


class CompetitiveAnalysisRun(): 
    def __init__(self, project_name, Description):
        self.project_name = project_name
        self.Description = Description

    def survey_post_process(self):
        survey = get_survey()
        if len(survey) < 100:
            raise TypeError("Expected survey too short.")
    
    def run(self,feedback,execute):
        CAC_inputs = {
                'feedback': feedback + execute.get('survey',''),
                'Description': self.Description,
                'project_name': self.project_name,
                'document_format_reference': self.BR_Initial_Template.get_whole_document(introduction= True),
                'original' : '' if 'all' in execute else get_survey()
            }
        run_with_retry(CompetitiveAnalysisCrew,
                            CAC_inputs,
                            name="CompetitiveAnalysisCrew",
                            post_process_callable=get_competitive_analysis)
  
class surveyRun():
    def __init__(self, project_name, Description, BR_Initial_Template):
        self.project_name = project_name
        self.Description = Description
        self.BR_Initial_Template = BR_Initial_Template

    def survey_post_process(self):
        survey = get_survey()
        if len(survey) < 100:
            raise TypeError("Expected survey too short.")
    
    def run(self,feedback,execute):
        CAC_inputs = {
                'feedback': feedback + execute.get('survey',''),
                'Description': self.Description,
                'project_name': self.project_name,
                'document_format_reference': self.BR_Initial_Template.get_whole_document(introduction= True),
                'original' : '' if 'all' in execute else get_survey()
            }
        run_with_retry(SurveyCrew,
                            CAC_inputs,
                            name="SurveyCrew",
                            post_process_callable=self.survey_post_process)


class ContextDiagramRun():
    def __init__(self, project_name, Description):
        self.project_name = project_name
        self.Description = Description

    def context_diagram_post_process(self):
        context_diagram = get_context_diagram()
        if len(context_diagram) < 300:
            raise TypeError("Expected context_diagram too short.") 
    
    def run(self,feedback,execute):
        DCD_inputs = {
                'feedback': feedback + execute.get('context_diagram',''),
                'survey': get_survey(),
                'project_name': self.project_name,
                'Description': self.Description,
                'original' : '' if 'all' in execute else get_context_diagram()
            }
        run_with_retry(DraftContentDiagramCrew, 
                        DCD_inputs, 
                        name="DraftContentDiagramCrew", 
                        post_process_callable=self.context_diagram_post_process)
        
class eventlistRun():
    def __init__(self, project_name, Description):
        self.project_name = project_name
        self.Description = Description

    def event_list_post_process(self):
        event_list = get_event_list()
        if len(event_list) < 100:
            raise TypeError("Expected event_list too short.") 
    
    def run(self,feedback,execute):
        DEL_inputs = {
                'feedback': feedback + execute.get('event_list',''),
                'context_diagram': get_context_diagram(),
                'project_name': self.project_name,
                'Description': self.Description,
                'original' : '' if 'all' in execute else get_event_list()
            }
        run_with_retry(DraftEventListCrew,
                        DEL_inputs,
                        name="DraftEventListCrew",
                        post_process_callable=self.event_list_post_process)

class UserIntroductionRun():
    def __init__(self, project_name, Description):
        self.project_name = project_name
        self.Description = Description

    def user_introduction_post_process(self):
        user_intro = get_user_introduction()
        if len(user_intro) < 100:
            raise TypeError("Expected user_intro too short.")
    
    def run(self,feedback,execute):
        UserIntroduction_inputs = {
                'feedback': feedback + execute.get('user_introduction',''),
                'reference':  get_reference(['context_diagram']),
                'project_name': self.project_name,
                'original' : '' if 'all' in execute else get_user_introduction()
            }
        run_with_retry(UserIntroductionDev, 
                    UserIntroduction_inputs, 
                    name="UserIntroductionDev", 
                    post_process_callable=self.user_introduction_post_process
                    )
        
        
class FeatureTreeRun():
    def __init__(self, project_name, Description):
        self.project_name = project_name
        self.Description = Description

    def feature_tree_post_process(self):
        feature_tree = get_feature_tree()
        if len(feature_tree) < 100:
            raise TypeError("Expected feature_tree too short.")
    
    def run(self,feedback,execute,initial_info):
        FeatureTree_inputs = {
                'feedback': feedback + execute.get('feature_tree',''),
                'initial_info': initial_info,
                'Description': self.Description,
                'project_name': self.project_name,
                'original' : '' if 'all' in execute else get_feature_tree()
            }
        run_with_retry(FeatureTreeDev, 
                    FeatureTree_inputs, 
                    name="FeatureTreeDev", 
                    post_process_callable=self.feature_tree_post_process,
                    )
        
class BusinessScopeRun():
    def __init__(self, project_name, Description):
        self.project_name = project_name
        self.Description = Description

    def business_scope_post_process(self):
        business_scope = get_business_scope()
        if len(business_scope) < 100:
            raise TypeError("Expected business_scope too short.")
    
    def run(self,feedback,execute):
        BusinessScope_inputs = {
                'feedback': feedback + execute.get('business_scope',''),
                'reference': get_reference(['feature_tree', 'context_diagram', 'event_list', 'user_introduction', 'survey']),
                'Description': self.Description,
                'project_name': self.project_name,
                'original' : '' if 'all' in execute else get_business_scope()
            }
        run_with_retry(BusinessScopeDev, 
                    BusinessScope_inputs, 
                    name="BusinessScopeDev", 
                    post_process_callable=self.business_scope_post_process,
                    )
