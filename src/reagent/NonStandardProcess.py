# src/reagent/NonStandardProcess.py — Stage 5: supplementary artifacts.
#
# Outline:
#   UsageScenariorun            wraps UsageScenarioCrew; depends on use_case
#   StateTransitionDiagramrun   wraps STDCrew; depends on use_case
#   NonStandardProcessrun(project_name, Description, artifact_planing)
#                               orders artifacts via topological_sort and
#                               executes each once in dependency order.
from RequirementElicitation import UsageScenarioCrew
from util import *
from RequirementAnalysis import  STDCrew, DialogMapCrew


class UsageScenariorun():
    def __init__(self, project_name, Description: str):
        self.project_name = project_name
        self.Description = Description
        self.dependencies = ['use_case']

    def usage_scenario_post_process(self):
            usage_scenario = get_usage_scenario()
            if len(usage_scenario) < 100:
                raise TypeError("Expected usage_scenario too short.")
    
    def run(self):
        US_inputs = {
            'project_name': self.project_name,
            'reference': get_reference(self.dependencies),
            'Description': self.Description,
        }
        run_with_retry(UsageScenarioCrew, 
                    US_inputs, 
                    name="UsageScenarioCrew",
                    post_process_callable=self.usage_scenario_post_process)

class StateTransitionDiagramrun():
    def __init__(self, project_name, Description: str):
        self.project_name = project_name
        self.Description = Description
        self.dependencies = ['use_case']
    def state_transition_diagram_post_process(self):
        state_transition_diagram = get_state_transition_diagram()
        if len(state_transition_diagram) < 100:
            raise TypeError("Expected state_transition_diagram too short.") 

    def run(self):
        STD_inputs = {
            'project_name': self.project_name,
            'reference': get_reference(self.dependencies),
        }
        run_with_retry(STDCrew, 
                   STD_inputs, 
                   name="STDCrew",
                   post_process_callable=self.state_transition_diagram_post_process)

def NonStandardProcessrun(project_name, Description: str, artifact_planing):
    order = topological_sort(to_artifact_DAG(artifact_planing))
    artifact_dict = {
        'usage_scenario': UsageScenariorun(project_name=project_name, Description=Description),
        'state_transition_diagram': StateTransitionDiagramrun(project_name=project_name, Description=Description),
    }
    for artifact in order:
        if artifact in artifact_dict:
            artifact_dict[artifact].run()
