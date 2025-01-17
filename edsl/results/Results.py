"""
The Results object is the result of running a survey. 
It is not typically instantiated directly, but is returned by the run method of a `Job` object.
"""

from __future__ import annotations
import json
import hashlib
import random
from collections import UserList, defaultdict
from typing import Optional, Callable, Any, Type, Union, List

from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import HtmlFormatter
from IPython.display import HTML

from simpleeval import EvalWithCompoundTypes

from edsl.exceptions.results import (
    ResultsBadMutationstringError,
    ResultsColumnNotFoundError,
    ResultsInvalidNameError,
    ResultsMutateError,
    ResultsFilterError,
)
from edsl.agents import Agent, AgentList
from edsl.language_models.LanguageModel import LanguageModel
from edsl.results.Dataset import Dataset
from edsl.results.Result import Result
from edsl.results.ResultsExportMixin import ResultsExportMixin
from edsl.scenarios import Scenario
from edsl.scenarios.ScenarioList import ScenarioList
from edsl.surveys import Survey
from edsl.data.Cache import Cache
from edsl.utilities import (
    is_valid_variable_name,
    shorten_string,
)
from edsl.utilities.decorators import add_edsl_version, remove_edsl_version
from edsl.utilities.utilities import dict_hash
from edsl.results.ResultsToolsMixin import ResultsToolsMixin

from edsl.results.ResultsDBMixin import ResultsDBMixin
from edsl.results.ResultsGGMixin import ResultsGGMixin

from edsl.Base import Base
from edsl.results.ResultsFetchMixin import ResultsFetchMixin


class Mixins(
    ResultsExportMixin,
    ResultsDBMixin,
    ResultsFetchMixin,
    ResultsGGMixin,
    ResultsToolsMixin,
):
    pass


class Results(UserList, Mixins, Base):
    """
    This class is a UserList of Result objects.

    It is instantiated with a `Survey` and a list of `Result` objects.
    It can be manipulated in various ways with select, filter, mutate, etc.
    It also has a list of created_columns, which are columns that have been created with `mutate` and are not part of the original data.
    """

    known_data_types = [
        "answer",
        "scenario",
        "agent",
        "model",
        "prompt",
        "raw_model_response",
        "iteration",
        "question_text",
        "question_options",
        "question_type",
        "comment",
    ]

    def __init__(
        self,
        survey: Optional[Survey] = None,
        data: Optional[list[Result]] = None,
        created_columns: Optional[list[str]] = None,
        cache: Optional[Cache] = None,
        job_uuid: Optional[str] = None,
        total_results: Optional[int] = None,
    ):
        """Instantiate a `Results` object with a survey and a list of `Result` objects.

        :param survey: A Survey object.
        :param data: A list of Result objects.
        :param created_columns: A list of strings that are created columns.
        :param job_uuid: A string representing the job UUID.
        :param total_results: An integer representing the total number of results.
        """
        super().__init__(data)
        self.survey = survey
        self.created_columns = created_columns or []
        self._job_uuid = job_uuid
        self._total_results = total_results
        self.cache = cache or Cache()

        if hasattr(self, "_add_output_functions"):
            self._add_output_functions()

    def code(self):
        raise NotImplementedError

    def __getitem__(self, i):
        if isinstance(i, int):
            return self.data[i]

        if isinstance(i, slice):
            return self.__class__(survey=self.survey, data=self.data[i])

        if isinstance(i, str):
            return self.to_dict()[i]

        raise TypeError("Invalid argument type")

    def _update_results(self) -> None:
        if self._job_uuid and len(self.data) < self._total_results:
            results = [
                Result(
                    agent=Agent.from_dict(json.loads(r.agent)),
                    scenario=Scenario.from_dict(json.loads(r.scenario)),
                    model=LanguageModel.from_dict(json.loads(r.model)),
                    iteration=1,
                    answer=json.loads(r.answer),
                )
                for r in CRUD.read_results(self._job_uuid)
            ]
            self.data = results

    def __add__(self, other: Results) -> Results:
        """Add two Results objects together.
        They must have the same survey and created columns.
        :param other: A Results object.

        Example:

        >>> r = Results.example()
        >>> r2 = Results.example()
        >>> r3 = r + r2
        """
        if self.survey != other.survey:
            raise Exception(
                "The surveys are not the same so they cannot be added together."
            )
        if self.created_columns != other.created_columns:
            raise Exception(
                "The created columns are not the same so they cannot be added together."
            )

        return Results(
            survey=self.survey,
            data=self.data + other.data,
            created_columns=self.created_columns,
        )

    def __repr__(self) -> str:
        return f"Results(data = {self.data}, survey = {repr(self.survey)}, created_columns = {self.created_columns})"

    def _repr_html_(self) -> str:
        json_str = json.dumps(self.to_dict()["data"], indent=4)
        formatted_json = highlight(
            json_str,
            JsonLexer(),
            HtmlFormatter(style="default", full=True, noclasses=True),
        )
        return HTML(formatted_json).data

    def _to_dict(self):
        return {
            "data": [result.to_dict() for result in self.data],
            "survey": self.survey.to_dict(),
            "created_columns": self.created_columns,
            "cache": Cache() if not hasattr(self, "cache") else self.cache.to_dict(),
        }

    @add_edsl_version
    def to_dict(self) -> dict[str, Any]:
        """Convert the Results object to a dictionary.

        The dictionary can be quite large, as it includes all of the data in the Results object.

        Example: Illustrating just the keys of the dictionary.

        >>> r = Results.example()
        >>> r.to_dict().keys()
        dict_keys(['data', 'survey', 'created_columns', 'cache', 'edsl_version', 'edsl_class_name'])
        """
        return self._to_dict()

    def __hash__(self) -> int:
        return dict_hash(self._to_dict())

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data: dict[str, Any]) -> Results:
        """Convert a dictionary to a Results object.

        :param data: A dictionary representation of a Results object.

        Example:

        >>> r = Results.example()
        >>> d = r.to_dict()
        >>> r2 = Results.from_dict(d)
        >>> r == r2
        True
        """
        results = cls(
            survey=Survey.from_dict(data["survey"]),
            data=[Result.from_dict(r) for r in data["data"]],
            created_columns=data.get("created_columns", None),
            cache=Cache.from_dict(data.get("cache")) if "cache" in data else Cache(),
        )
        return results

    ######################
    ## Convenience methods
    ## & Report methods
    ######################
    @property
    def _key_to_data_type(self) -> dict[str, str]:
        """
        Return a mapping of keys (how_feeling, status, etc.) to strings representing data types.

        Objects such as Agent, Answer, Model, Scenario, etc.
        - Uses the key_to_data_type property of the Result class.
        - Includes any columns that the user has created with `mutate`
        """
        d = {}
        for result in self.data:
            d.update(result.key_to_data_type)
        for column in self.created_columns:
            d[column] = "answer"
        return d

    @property
    def _data_type_to_keys(self) -> dict[str, str]:
        """
        Return a mapping of strings representing data types (objects such as Agent, Answer, Model, Scenario, etc.) to keys (how_feeling, status, etc.)
        - Uses the key_to_data_type property of the Result class.
        - Includes any columns that the user has created with `mutate`

        Example:

        >>> r = Results.example()
        >>> r._data_type_to_keys
        defaultdict(...
        """
        d: dict = defaultdict(set)
        for result in self.data:
            for key, value in result.key_to_data_type.items():
                d[value] = d[value].union(set({key}))
        for column in self.created_columns:
            d["answer"] = d["answer"].union(set({column}))
        return d

    @property
    def columns(self) -> list[str]:
        """Return a list of all of the columns that are in the Results.

        Example:

        >>> r = Results.example()
        >>> r.columns
        ['agent.agent_instruction', ...]
        """
        column_names = [f"{v}.{k}" for k, v in self._key_to_data_type.items()]
        return sorted(column_names)

    @property
    def answer_keys(self) -> dict[str, str]:
        """Return a mapping of answer keys to question text.

        Example:

        >>> r = Results.example()
        >>> r.answer_keys
        {'how_feeling': 'How are you this {{ period }}?', 'how_feeling_yesterday': 'How were you feeling yesterday {{ period }}?'}
        """
        if not self.survey:
            raise Exception("Survey is not defined so no answer keys are available.")

        answer_keys = self._data_type_to_keys["answer"]
        answer_keys = {k for k in answer_keys if "_comment" not in k}
        questions_text = [
            self.survey.get_question(k).question_text for k in answer_keys
        ]
        short_question_text = [shorten_string(q, 80) for q in questions_text]
        initial_dict = dict(zip(answer_keys, short_question_text))
        sorted_dict = {key: initial_dict[key] for key in sorted(initial_dict)}
        return sorted_dict

    @property
    def agents(self) -> AgentList:
        """Return a list of all of the agents in the Results.

        Example:

        >>> r = Results.example()
        >>> r.agents
        AgentList([Agent(traits = {'status': 'Joyful'}), Agent(traits = {'status': 'Joyful'}), Agent(traits = {'status': 'Sad'}), Agent(traits = {'status': 'Sad'})])
        """
        return AgentList([r.agent for r in self.data])

    @property
    def models(self) -> list[Type[LanguageModel]]:
        """Return a list of all of the models in the Results.

        Example:

        >>> r = Results.example()
        >>> r.models[0]
        Model(model_name = 'gpt-4-1106-preview', temperature = 0.5, max_tokens = 1000, top_p = 1, frequency_penalty = 0, presence_penalty = 0, logprobs = False, top_logprobs = 3)
        """
        return [r.model for r in self.data]

    @property
    def scenarios(self) -> ScenarioList:
        """Return a list of all of the scenarios in the Results.

        Example:

        >>> r = Results.example()
        >>> r.scenarios
        ScenarioList([Scenario({'period': 'morning'}), Scenario({'period': 'afternoon'}), Scenario({'period': 'morning'}), Scenario({'period': 'afternoon'})])
        """
        return ScenarioList([r.scenario for r in self.data])

    @property
    def agent_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Agent data.

        Example:

        >>> r = Results.example()
        >>> r.agent_keys
        ['agent_instruction', 'agent_name', 'status']
        """
        return sorted(self._data_type_to_keys["agent"])

    @property
    def model_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the LanguageModel data.

        >>> r = Results.example()
        >>> r.model_keys
        ['frequency_penalty', 'logprobs', 'max_tokens', 'model', 'presence_penalty', 'temperature', 'top_logprobs', 'top_p']
        """
        return sorted(self._data_type_to_keys["model"])

    @property
    def scenario_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Scenario data.

        >>> r = Results.example()
        >>> r.scenario_keys
        ['period']
        """
        return sorted(self._data_type_to_keys["scenario"])

    @property
    def question_names(self) -> list[str]:
        """Return a list of all of the question names.

        Example:

        >>> r = Results.example()
        >>> r.question_names
        ['how_feeling', 'how_feeling_yesterday']
        """
        if self.survey is None:
            return []
        return sorted(list(self.survey.question_names))

    @property
    def all_keys(self) -> list[str]:
        """Return a set of all of the keys that are in the Results.

        Example:

        >>> r = Results.example()
        >>> r.all_keys
        ['agent_instruction', 'agent_name', 'frequency_penalty', 'how_feeling', 'how_feeling_yesterday', 'logprobs', 'max_tokens', 'model', 'period', 'presence_penalty', 'status', 'temperature', 'top_logprobs', 'top_p']
        """
        answer_keys = set(self.answer_keys)
        all_keys = (
            answer_keys.union(self.agent_keys)
            .union(self.scenario_keys)
            .union(self.model_keys)
        )
        return sorted(list(all_keys))

    def _parse_column(self, column: str) -> tuple[str, str]:
        """
        Parses a column name into a tuple containing a data type and a key.

        >>> r = Results.example()
        >>> r._parse_column("answer.how_feeling")
        ('answer', 'how_feeling')

        The standard way a column is specified is with a dot-separated string, e.g. _parse_column("agent.status")
        But you can also specify a single key, e.g. "status", in which case it will look up the data type.
        """
        if "." in column:
            data_type, key = column.split(".")
        else:
            try:
                data_type, key = self._key_to_data_type[column], column
            except KeyError:
                import difflib

                close_matches = difflib.get_close_matches(
                    column, self._key_to_data_type.keys()
                )
                if close_matches:
                    suggestions = ", ".join(close_matches)
                    raise ResultsColumnNotFoundError(
                        f"Column '{column}' not found in data. Did you mean: {suggestions}?"
                    )
                else:
                    raise ResultsColumnNotFoundError(
                        f"Column {column} not found in data"
                    )
        return data_type, key

    def first(self) -> Result:
        """Return the first observation in the results.

        Example:

        >>> r = Results.example()
        >>> r.first()
        Result(agent...
        """
        return self.data[0]

    def answer_truncate(self, column: str, top_n=5, new_var_name=None) -> Results:
        """Create a new variable that truncates the answers to the top_n.

        :param column: The column to truncate.
        :param top_n: The number of top answers to keep.
        :param new_var_name: The name of the new variable. If None, it is the original name + '_truncated'.



        """
        if new_var_name is None:
            new_var_name = column + "_truncated"
        answers = list(self.select(column).tally().keys())

        def f(x):
            if x in answers[:top_n]:
                return x
            else:
                return "Other"

        return self.recode(column, recode_function=f, new_var_name=new_var_name)

    def recode(
        self, column: str, recode_function: Optional[Callable], new_var_name=None
    ) -> Results:
        """
        Recode a column in the Results object.

        >>> r = Results.example()
        >>> r.recode('how_feeling', recode_function = lambda x: 1 if x == 'Great' else 0).select('how_feeling', 'how_feeling_recoded')
        Dataset([{'answer.how_feeling': ['OK', 'Great', 'Terrible', 'OK']}, {'answer.how_feeling_recoded': [0, 1, 0, 0]}])
        """

        if new_var_name is None:
            new_var_name = column + "_recoded"
        new_data = []
        for result in self.data:
            new_result = result.copy()
            value = new_result.get_value("answer", column)
            # breakpoint()
            new_result["answer"][new_var_name] = recode_function(value)
            new_data.append(new_result)

        # print("Created new variable", new_var_name)
        return Results(
            survey=self.survey,
            data=new_data,
            created_columns=self.created_columns + [new_var_name],
        )
    
    def add_column(self, column_name: str, values: list) -> Results:
        """Adds columns to Results
        
        >>> r = Results.example()
        >>> r.add_column('a', [1,2,3,]).select('a')
        Dataset([{'answer.a': [1, 2, 3]}])
        """

        assert len(values) == len(self.data), "The number of values must match the number of results."
        new_results = self.data.copy()
        for i, result in enumerate(new_results):
            result["answer"][column_name] = values[i]
        return Results(survey=self.survey, data=new_results, created_columns=self.created_columns + [column_name])
    
    def add_columns_from_dict(self, columns: List[dict]) -> Results:
        keys = list(columns[0].keys())
        for key in keys:
            values = [d[key] for d in columns]
            self = self.add_column(key, values)
        return self


    def mutate(
        self, new_var_string: str, functions_dict: Optional[dict] = None
    ) -> Results:
        """
        Creates a value in the Results object as if has been asked as part of the survey.

        :param new_var_string: A string that is a valid Python expression.
        :param functions_dict: A dictionary of functions that can be used in the expression. The keys are the function names and the values are the functions themselves.

        It splits the new_var_string at the "=" and uses simple_eval

        Example:

        >>> r = Results.example()
        >>> r.mutate('how_feeling_x = how_feeling + "x"').select('how_feeling_x')
        Dataset([{'answer.how_feeling_x': ...
        """
        # extract the variable name and the expression
        if "=" not in new_var_string:
            raise ResultsBadMutationstringError(
                f"Mutate requires an '=' in the string, but '{new_var_string}' doesn't have one."
            )
        raw_var_name, expression = new_var_string.split("=", 1)
        var_name = raw_var_name.strip()
        if not is_valid_variable_name(var_name):
            raise ResultsInvalidNameError(f"{var_name} is not a valid variable name.")

        # create the evaluator
        functions_dict = functions_dict or {}

        def create_evaluator(result: Result) -> EvalWithCompoundTypes:
            return EvalWithCompoundTypes(
                names=result.combined_dict, functions=functions_dict
            )

        def new_result(old_result: Result, var_name: str) -> Result:
            evaluator = create_evaluator(old_result)
            value = evaluator.eval(expression)
            new_result = old_result.copy()
            new_result["answer"][var_name] = value
            return new_result

        try:
            new_data = [new_result(result, var_name) for result in self.data]
        except Exception as e:
            raise ResultsMutateError(f"Error in mutate. Exception:{e}")

        return Results(
            survey=self.survey,
            data=new_data,
            created_columns=self.created_columns + [var_name],
        )

    def rename(self, old_name: str, new_name: str) -> Results:
        """Rename an answer column in a Results object.

        >>> s = Results.example()
        >>> s.rename('how_feeling', 'how_feeling_new').select('how_feeling_new')
        Dataset([{'answer.how_feeling_new': ['OK', 'Great', 'Terrible', 'OK']}])

        # TODO: Should we allow renaming of scenario fields as well? Probably.

        """

        for obs in self.data:
            obs["answer"][new_name] = obs["answer"][old_name]
            del obs["answer"][old_name]

        return self

    def shuffle(self, seed: Optional[str] = "edsl") -> Results:
        """Shuffle the results.

        Example:

        >>> r = Results.example()
        >>> r.shuffle(seed = 1)[0]
        Result(...)
        """
        if seed != "edsl":
            seed = random.seed(seed)

        new_data = self.data.copy()
        random.shuffle(new_data)
        return Results(survey=self.survey, data=new_data, created_columns=None)

    def sample(
        self,
        n: int = None,
        frac: float = None,
        with_replacement: bool = True,
        seed: Optional[str] = "edsl",
    ) -> Results:
        """Sample the results.

        :param n: An integer representing the number of samples to take.
        :param frac: A float representing the fraction of samples to take.
        :param with_replacement: A boolean representing whether to sample with replacement.
        :param seed: An integer representing the seed for the random number generator.

        Example:

        >>> r = Results.example()
        >>> len(r.sample(2))
        2
        """
        if seed != "edsl":
            random.seed(seed)

        if n is None and frac is None:
            raise Exception("You must specify either n or frac.")

        if n is not None and frac is not None:
            raise Exception("You cannot specify both n and frac.")

        if frac is not None and n is None:
            n = int(frac * len(self.data))

        if with_replacement:
            new_data = random.choices(self.data, k=n)
        else:
            new_data = random.sample(self.data, n)

        return Results(survey=self.survey, data=new_data, created_columns=None)

    def select(self, *columns: Union[str, list[str]]) -> Dataset:
        """
        Select data from the results and format it.

        :param columns: A list of strings, each of which is a column name. The column name can be a single key, e.g. "how_feeling", or a dot-separated string, e.g. "answer.how_feeling".

        Example:

        >>> results = Results.example()
        >>> results.select('how_feeling')
        Dataset([{'answer.how_feeling': ['OK', 'Great', 'Terrible', 'OK']}])
        """
        if len(self) == 0:
            raise Exception("No data to select from---the Results object is empty.")

        if not columns or columns == ("*",) or columns == (None,):
            columns = ("*.*",)

        if isinstance(columns[0], list):
            columns = tuple(columns[0])

        def get_data_types_to_return(parsed_data_type):
            if parsed_data_type == "*":  # they want all of the columns
                return self.known_data_types
            else:
                if parsed_data_type not in self.known_data_types:
                    raise Exception(
                        f"Data type {parsed_data_type} not found in data. Did you mean one of {self.known_data_types}"
                    )
                return [parsed_data_type]

        # we're doing to populate this with the data we want to fetch
        to_fetch = defaultdict(list)

        new_data = []
        items_in_order = []
        # iterate through the passed columns
        for column in columns:
            # a user could pass 'result.how_feeling' or just 'how_feeling'
            parsed_data_type, parsed_key = self._parse_column(column)
            data_types = get_data_types_to_return(parsed_data_type)
            found_once = False  # we need to track this to make sure we found the key at least once

            for data_type in data_types:
                # the keys for that data_type e.g.,# if data_type is 'answer', then the keys are 'how_feeling', 'how_feeling_comment', etc.
                relevant_keys = self._data_type_to_keys[data_type]

                for key in relevant_keys:
                    if key == parsed_key or parsed_key == "*":
                        found_once = True
                        to_fetch[data_type].append(key)
                        items_in_order.append(data_type + "." + key)

            if not found_once:
                raise Exception(f"Key {parsed_key} not found in data.")

        for data_type in to_fetch:
            for key in to_fetch[data_type]:
                entries = self._fetch_list(data_type, key)
                new_data.append({data_type + "." + key: entries})

        def sort_by_key_order(dictionary):
            # Extract the single key from the dictionary
            single_key = next(iter(dictionary))
            # Return the index of this key in the list_of_keys
            return items_in_order.index(single_key)

        sorted(new_data, key=sort_by_key_order)

        return Dataset(new_data)

    def sort_by(self, columns, reverse: bool = False) -> Results:
        """Sort the results by one or more columns.

        :param columns: A string or a list of strings that are column names.
        :param reverse: A boolean that determines whether to sort in reverse order.

        Each column name can be a single key, e.g. "how_feeling", or a dot-separated string, e.g. "answer.how_feeling".

        Example:

        >>> r = Results.example()
        >>> r.sort_by(['how_feeling'], reverse=False).select('how_feeling').print()
        ┏━━━━━━━━━━━━━━┓
        ┃ answer       ┃
        ┃ .how_feeling ┃
        ┡━━━━━━━━━━━━━━┩
        │ Great        │
        ├──────────────┤
        │ OK           │
        ├──────────────┤
        │ OK           │
        ├──────────────┤
        │ Terrible     │
        └──────────────┘
        >>> r.sort_by(['how_feeling'], reverse=True).select('how_feeling').print()
        ┏━━━━━━━━━━━━━━┓
        ┃ answer       ┃
        ┃ .how_feeling ┃
        ┡━━━━━━━━━━━━━━┩
        │ Terrible     │
        ├──────────────┤
        │ OK           │
        ├──────────────┤
        │ OK           │
        ├──────────────┤
        │ Great        │
        └──────────────┘
        """
        if isinstance(columns, str):
            columns = [columns]

        def to_numeric_if_possible(v):
            try:
                return float(v)
            except:
                return v

        def sort_key(item):
            # Create an empty list to store the key components for sorting
            key_components = []

            # Loop through each column specified in the sort
            for col in columns:
                # Parse the column into its data type and key
                data_type, key = self._parse_column(col)

                # Retrieve the value from the item based on the parsed data type and key
                value = item.get_value(data_type, key)

                # Convert the value to numeric if possible, and append it to the key components
                key_components.append(to_numeric_if_possible(value))

            # Convert the list of key components into a tuple to serve as the sorting key
            return tuple(key_components)

        new_data = sorted(
            self.data,
            key=sort_key,
            reverse=reverse,
        )
        return Results(survey=self.survey, data=new_data, created_columns=None)

    def filter(self, expression: str) -> Results:
        """
        Filter based on the given expression and returns the filtered `Results`.

        :param expression: A string expression that evaluates to a boolean. The expression is applied to each element in `Results` to determine whether it should be included in the filtered results.

        The `expression` parameter is a string that must resolve to a boolean value when evaluated against each element in `Results`.
        This expression is used to determine which elements to include in the returned `Results`.

        Example usage: Create an example `Results` instance and apply filters to it:

        >>> r = Results.example()
        >>> r.filter("how_feeling == 'Great'").select('how_feeling').print()
        ┏━━━━━━━━━━━━━━┓
        ┃ answer       ┃
        ┃ .how_feeling ┃
        ┡━━━━━━━━━━━━━━┩
        │ Great        │
        └──────────────┘

        Example usage: Using an OR operator in the filter expression.

        >>> r = Results.example().filter("how_feeling = 'Great'").select('how_feeling').print()
        Traceback (most recent call last):
        ...
        edsl.exceptions.results.ResultsFilterError: You must use '==' instead of '=' in the filter expression.

        >>> r.filter("how_feeling == 'Great' or how_feeling == 'Terrible'").select('how_feeling').print()
        ┏━━━━━━━━━━━━━━┓
        ┃ answer       ┃
        ┃ .how_feeling ┃
        ┡━━━━━━━━━━━━━━┩
        │ Great        │
        ├──────────────┤
        │ Terrible     │
        └──────────────┘
        """

        def has_single_equals(string):
            if "!=" in string:
                return False
            if "=" in string and not "==" in string:
                return True

        if has_single_equals(expression):
            raise ResultsFilterError(
                "You must use '==' instead of '=' in the filter expression."
            )

        def create_evaluator(result):
            """Create an evaluator for the given result.
            The 'combined_dict' is a mapping of all values for that Result object.
            """
            return EvalWithCompoundTypes(names=result.combined_dict)

        try:
            # iterates through all the results and evaluates the expression
            new_data = [
                result
                for result in self.data
                if create_evaluator(result).eval(expression)
            ]
        except Exception as e:
            raise ResultsFilterError(
                f"""Error in filter. Exception:{e}.
            The expression you provided was: {expression}. 
            Please make sure that the expression is a valid Python expression that evaluates to a boolean.
            For example, 'how_feeling == "Great"' is a valid expression, as is 'how_feeling in ["Great", "Terrible"]'.
            However, 'how_feeling = "Great"' is not a valid expression.

            See https://docs.expectedparrot.com/en/latest/results.html#filtering-results for more details.
            """
            )

        if len(new_data) == 0:
            import warnings

            warnings.warn("No results remain after applying the filter.")

        return Results(survey=self.survey, data=new_data, created_columns=None)

    @classmethod
    def example(cls, debug: bool = False) -> Results:
        """Return an example `Results` object.

        Example usage:

        >>> r = Results.example()

        :param debug: if False, uses actual API calls
        """
        from edsl.jobs import Jobs
        from edsl.data.Cache import Cache

        c = Cache()
        job = Jobs.example()
        results = job.run(cache=c, debug=debug)
        return results

    def rich_print(self):
        """Display an object as a table."""
        pass
        # with io.StringIO() as buf:
        #     console = Console(file=buf, record=True)

        #     for index, result in enumerate(self):
        #         console.print(f"Result {index}")
        #         console.print(result.rich_print())

        #     return console.export_text()

    def __str__(self):
        data = self.to_dict()["data"]
        return json.dumps(data, indent=4)

    def show_exceptions(self, traceback=False):
        """Print the exceptions."""
        if hasattr(self, "task_history"):
            self.task_history.show_exceptions(traceback)
        else:
            print("No exceptions to show.")

    def score(self, f: Callable) -> list:
        """Score the results using in a function.

        :param f: A function that takes values from a Resul object and returns a score.

        >>> r = Results.example()
        >>> def f(status): return 1 if status == 'Joyful' else 0
        >>> r.score(f)
        [1, 1, 0, 0]
        """
        return [r.score(f) for r in self.data]


def main():  # pragma: no cover
    """Call the OpenAI API credits."""
    from edsl.results.Results import Results

    results = Results.example(debug=True)
    print(results.filter("how_feeling == 'Great'").select("how_feeling"))
    print(results.mutate("how_feeling_x = how_feeling + 'x'").select("how_feeling_x"))


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)
