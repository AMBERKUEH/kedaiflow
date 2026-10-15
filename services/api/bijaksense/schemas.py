from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator
from .config import COMMODITIES


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True, allow_inf_nan=False)


class ContextInput(Model):
    industry: str = Field(min_length=2, max_length=80)
    location: str = Field(min_length=2, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    products: list[str] = Field(default_factory=list, max_length=30)
    materials: list[str] = Field(default_factory=list, max_length=30)
    markets: list[str] = Field(default_factory=lambda: ['Malaysia'], max_length=20)
    commodities: list[str] = Field(default_factory=list, max_length=10)
    cost_categories: dict[str, str] = Field(default_factory=dict, max_length=10)
    enabled: bool = True

    @field_validator('products', 'materials', 'markets')
    @classmethod
    def bounded_tags(cls, values):
        if any(not 1 <= len(v.strip()) <= 80 for v in values):
            raise ValueError('Each term must contain 1–80 characters')
        return list(dict.fromkeys(v.strip().lower() for v in values))

    @model_validator(mode='after')
    def selected_commodities(self):
        if any(k not in COMMODITIES for k in self.commodities):
            raise ValueError('Choose a supported commodity benchmark')
        if any(k not in self.commodities or len(v) > 80 for k, v in self.cost_categories.items()):
            raise ValueError('Cost categories must map selected benchmarks to short cost labels')
        return self


class CompetitorInput(Model):
    name: str = Field(min_length=2, max_length=120)
    url: str = Field(max_length=1500)
    source_type: Literal['website', 'rss'] = 'website'
    public_access_confirmed: Literal[True]


class FeedbackInput(Model):
    status: Literal['acknowledged', 'dismissed', 'useful', 'not_relevant', 'new']
    note: str = Field(default='', max_length=1000)


class LLMChoice(Model):
    candidate_id: str
    action_codes: list[str] = Field(min_length=1, max_length=3)


class RecommendationOutput(Model):
    choices: list[LLMChoice] = Field(max_length=15)
