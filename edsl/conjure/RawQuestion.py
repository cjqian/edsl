from dataclasses import dataclass, field
from typing import List, Optional, Union
from edsl.questions import QuestionBase
from edsl import Question

from edsl.conjure.utilities import convert_value


@dataclass
class RawQuestion:
    question_type: str
    question_name: str
    question_text: str
    responses: List[str] = field(default_factory=list)
    question_options: Optional[List[str]] = None

    def __post_init__(self):
        self.responses = [convert_value(r) for r in self.responses]

    def to_question(self) -> QuestionBase:
        """Return a Question object from the RawQuestion."""

        # TODO: Remove this once we have a better way to handle multiple_choice_with_other
        if self.question_type == "multiple_choice_with_other":
            question_type = "multiple_choice"
        else:
            question_type = self.question_type

        # exclude responses from the dictionary if they have a None value; don't inlcude responses in the dictionary
        d = {
            k: v
            for k, v in {
                "question_type": question_type,
                "question_name": self.question_name,
                "question_text": self.question_text,
                "responses": self.responses,
                "question_options": self.question_options,
            }.items()
            if v is not None and k != "responses"
        }
        return Question(**d)
