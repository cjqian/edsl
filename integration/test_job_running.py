import pytest


def test_handle_model_exception():
    import random
    from edsl.language_models.LanguageModel import LanguageModel
    from edsl.enums import LanguageModelType, InferenceServiceType
    import asyncio
    from typing import Any
    from edsl import Scenario
    from edsl import Survey

    from httpcore import ConnectionNotAvailable
    from edsl.questions import QuestionFreeText

    def create_exception_throwing_model(exception: Exception, fail_at_number: int):
        class TestLanguageModelGood(LanguageModel):
            _model_ = LanguageModelType.TEST.value
            _parameters_ = {"temperature": 0.5, "use_cache": False}
            _inference_service_ = InferenceServiceType.TEST.value

            counter = 0

            async def async_execute_model_call(
                self, user_prompt: str, system_prompt: str
            ) -> dict[str, Any]:
                await asyncio.sleep(0.1)
                self.counter += 1
                if self.counter == fail_at_number:
                    raise exception
                return {"message": """{"answer": "SPAM!"}"""}

            def parse_response(self, raw_response: dict[str, Any]) -> str:
                return raw_response["message"]

        return TestLanguageModelGood()

    def create_survey(num_questions: int, chained: bool = True):
        survey = Survey()
        for i in range(num_questions):
            q = QuestionFreeText(
                question_text=f"How are you?", question_name=f"question_{i}"
            )
            survey.add_question(q)
            if i > 0 and chained:
                survey.add_targeted_memory(f"question_{i}", f"question_{i-1}")
        return survey

    ### Tasks are Not Chained
    FAIL_AT_NUMBER = 6
    target_exception = ConnectionNotAvailable
    model = create_exception_throwing_model(
        target_exception, fail_at_number=FAIL_AT_NUMBER
    )
    survey = create_survey(num_questions=20, chained=False)
    results = survey.by(model).run()
    assert results.select(f"answer.question_{FAIL_AT_NUMBER -1}").first() is None
    assert results.select(f"answer.question_{FAIL_AT_NUMBER + 1}").first() == "SPAM!"

    ### Tasks are Chained
    ### If there is a failure, it should cascade to all follow-on tasks
    FAIL_AT_NUMBER = 6
    target_exception = ConnectionNotAvailable
    model = create_exception_throwing_model(
        target_exception, fail_at_number=FAIL_AT_NUMBER
    )
    # survey = create_survey(num_questions=20, chained=False)
    # results = survey.by(model).run()
    # assert results.select(f"answer.question_{FAIL_AT_NUMBER -1}").first() is None
    # assert results.select(f"answer.question_{FAIL_AT_NUMBER + 1}").first() is None


if __name__ == "__main__":
    test_handle_model_exception()
