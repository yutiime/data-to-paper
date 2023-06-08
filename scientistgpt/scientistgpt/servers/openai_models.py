from dataclasses import dataclass
from typing import List, Tuple

from scientistgpt.utils.types import IndexOrderedEnum


MODEL_ENGINE_TO_MAX_TOKENS_AND_IN_OUT_DOLLAR = {
    "gpt-3.5-turbo": (4096, 0.002, 0.002),
    "gpt-4": (8192, 0.03, 0.06),
    # "gpt-4-32k": 32768,
}


class ModelEngine(IndexOrderedEnum):
    """
    Enum for the different model engines available in openai.
    Support comparison operators, according to the order of the enum.
    """
    GPT35_TURBO = "gpt-3.5-turbo"
    GPT4 = "gpt-4"
    GPT4_32 = "gpt-4-32k"

    def __str__(self):
        return self.value

    def __repr__(self):
        return self.value

    def __hash__(self):
        return hash(self.value)

    @property
    def max_tokens(self):
        return MODEL_ENGINE_TO_MAX_TOKENS_AND_IN_OUT_DOLLAR[self.value][0]

    @property
    def pricing(self) -> Tuple[float, float]:
        """
        Return the pricing for the model engine.
        (in_dollar_per_token, out_dollar_per_token)
        """
        return MODEL_ENGINE_TO_MAX_TOKENS_AND_IN_OUT_DOLLAR[self.value][1:]


@dataclass
class OpenaiCallParameters:
    """
    Parameters for calling OpenAI API.
    """
    model_engine: ModelEngine = None
    temperature: float = None
    max_tokens: int = None
    top_p: float = None
    frequency_penalty: float = None
    presence_penalty: float = None
    stop: List[str] = None

    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v is not None}

    def __str__(self):
        return str(self.to_dict())

    def is_all_none(self):
        return all(v is None for v in self.to_dict().values())


OPENAI_CALL_PARAMETERS_NAMES = list(OpenaiCallParameters.__dataclass_fields__.keys())
