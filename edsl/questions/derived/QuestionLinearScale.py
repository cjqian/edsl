"""This module contains the QuestionLinearScale class. It is a subclass of the QuestionMultipleChoice class and is used to create linear scale questions.
Example usage:

.. code-block:: python

    from edsl.questions import QuestionLinearScale

    q = QuestionLinearScale(
        question_name = "studying",
        question_text = "On a scale from 0 to 5, how much do you enjoy studying? (0 = not at all, 5 = very much)",
        question_options = [0, 1, 2, 3, 4, 5]
    )

"""
from __future__ import annotations
import textwrap
from typing import Optional
from edsl.questions.descriptors import QuestionOptionsDescriptor, OptionLabelDescriptor
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice


class QuestionLinearScale(QuestionMultipleChoice):
    """
    This question asks the respondent to respond to a statement on a linear scale.

    :param question_name: The name of the question.
    :type question_name: str
    :param question_text: The text of the question.
    :type question_text: str
    :param question_options: The options the respondent should select from.
    :type question_options: list[int]
    :param option_labels: maps question_options to labels.
    :type option_labels: dict[int, str], optional
    :param instructions: Instructions for the question. If not provided, the default instructions are used. To view them, run `QuestionLinearScale.default_instructions`.
    :type instructions: str, optional
    :param short_names_dict: Maps question_options to short names.
    :type short_names_dict: dict[str, str], optional

    For an example, see `QuestionLinearScale.example()`.
    """

    question_type = "linear_scale"
    option_labels: Optional[dict[int, str]] = OptionLabelDescriptor()
    question_options = QuestionOptionsDescriptor(linear_scale=True)

    def __init__(
        self,
        question_text: str,
        question_options: list[int],
        question_name: str,
        short_names_dict: Optional[dict[str, str]] = None,
        option_labels: Optional[dict[int, str]] = None,
    ):
        """Instantiate a new QuestionLinearScale."""
        super().__init__(
            question_text=question_text,
            question_options=question_options,
            question_name=question_name,
            short_names_dict=short_names_dict,
        )
        self.question_options = question_options
        self.option_labels = option_labels

    ################
    # Helpful
    ################
    @classmethod
    def example(cls) -> QuestionLinearScale:
        """Return an example of a linear scale question."""
        return cls(
            question_text="How much do you like ice cream?",
            question_options=[1, 2, 3, 4, 5],
            question_name="ice_cream",
            option_labels={1: "I hate it", 5: "I love it"},
        )


def main():
    """Create an example of a linear scale question and demonstrate its functionality."""
    from edsl.questions.derived.QuestionLinearScale import QuestionLinearScale

    q = QuestionLinearScale.example()
    q.question_text
    q.question_options
    q.question_name
    q.short_names_dict
    # validate an answer
    q.validate_answer({"answer": 3, "comment": "I like custard"})
    # translate answer code
    q.translate_answer_code_to_answer(3, {})
    # simulate answer
    q.simulate_answer()
    q.simulate_answer(human_readable=False)
    q.validate_answer(q.simulate_answer(human_readable=False))
    # serialization (inherits from Question)
    q.to_dict()
    assert q.from_dict(q.to_dict()) == q
