from typing import Optional, Callable
from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import FunctionDescriptor
import inspect

from edsl.questions.QuestionBase import QuestionBase
from edsl.questions.descriptors import FunctionDescriptor

from edsl.utilities.restricted_python import create_restricted_function


class QuestionFunctional(QuestionBase):
    """A special type of question that is *not* answered by an LLM."""

    question_type = "functional"
    default_instructions = ""
    activated = True
    function_source_code = ""
    function_name = ""

    def __init__(
        self,
        question_name: str,
        func: Optional[Callable] = None,
        question_text: Optional[str] = "Functional question",
        requires_loop: Optional[bool] = False,
        function_source_code: Optional[str] = None,
        function_name: Optional[str] = None,
    ):
        super().__init__()
        if func:
            self.function_source_code = inspect.getsource(func)
            self.function_name = func.__name__
        else:
            self.function_source_code = function_source_code
            self.function_name = function_name

        self.requires_loop = requires_loop

        self.func = create_restricted_function(
            self.function_name, self.function_source_code
        )

        self.question_name = question_name
        self.question_text = question_text
        self.instructions = self.default_instructions

    def activate(self):
        self.activated = True

    def activate_loop(self):
        """Activate the function with loop logic using RestrictedPython."""
        self.func = create_restricted_function(
            self.function_name, self.function_source_code, loop_activated=True
        )

    def answer_question_directly(self, scenario, agent_traits=None):
        """Return the answer to the question, ensuring the function is activated."""
        if not self.activated:
            raise Exception("Function not activated. Please activate it first.")
        try:
            return {"answer": self.func(scenario, agent_traits), "comment": None}
        except Exception as e:
            print("Function execution error:", e)
            raise Exception("Error during function execution.")

    def _translate_answer_code_to_answer(self, answer, scenario):
        """Required by Question, but not used by QuestionFunctional."""
        return None

    def _simulate_answer(self, human_readable=True) -> dict[str, str]:
        """Required by Question, but not used by QuestionFunctional."""
        raise NotImplementedError

    def _validate_answer(self, answer: dict[str, str]):
        """Required by Question, but not used by QuestionFunctional."""
        raise NotImplementedError

    def to_dict(self):
        return {
            "question_name": self.question_name,
            "function_source_code": self.function_source_code,
            "question_type": "functional",
            "requires_loop": self.requires_loop,
            "function_name": self.function_name,
        }

    @classmethod
    def example(cls):
        return cls(
            question_name="sum_and_multiply",
            func=calculate_sum_and_multiply,
            question_text="Calculate the sum of the list and multiply it by the agent trait multiplier.",
            requires_loop=True,
        )


def calculate_sum_and_multiply(scenario, agent_traits):
    numbers = scenario.get("numbers", [])
    multiplier = agent_traits.get("multiplier", 1) if agent_traits else 1
    sum = 0
    for num in numbers:
        sum = sum + num
    return sum * multiplier


def main():
    from edsl import Scenario, Agent
    from edsl.questions.QuestionFunctional import QuestionFunctional

    # Create an instance of QuestionFunctional with the new function
    question = QuestionFunctional.example()

    # Activate and test the function
    question.activate()
    scenario = Scenario({"numbers": [1, 2, 3, 4, 5]})
    agent = Agent(traits={"multiplier": 10})
    results = question.by(scenario).by(agent).run()
    print(results)
