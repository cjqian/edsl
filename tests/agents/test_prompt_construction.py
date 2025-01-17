import pytest

from edsl import Agent
from edsl.questions import QuestionMultipleChoice as q


def test_system_prompt_traits_passed():
    agent = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
    i = agent._create_invigilator(question=q.example())
    system_prompt = i.construct_system_prompt()
    assert True == all([key in system_prompt for key in agent.traits.keys()])


def test_user_prompt_question_text_passed():
    agent = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
    from edsl.questions import QuestionMultipleChoice as q

    i = agent._create_invigilator(question=q.example())
    user_prompt = i.construct_user_prompt()
    assert q.example().question_text in user_prompt


def test_scenario_render_in_user_prompt():
    from edsl.questions import QuestionFreeText
    from edsl.scenarios import Scenario
    from edsl import Agent

    agent = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
    q = QuestionFreeText(
        question_text="How are you today {{name}}?", question_name="name"
    )
    s = Scenario({'name': 'Peter'})
    i = agent._create_invigilator(question=q, scenario=s)
    user_prompt = i.construct_user_prompt()
    assert "Peter" in user_prompt
