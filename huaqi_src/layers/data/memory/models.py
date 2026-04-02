from typing import Dict
from pydantic import BaseModel, Field


class VectorDocument(BaseModel):
    id: str
    user_id: str
    content: str
    metadata: Dict = Field(default_factory=dict)


class VectorQuery(BaseModel):
    user_id: str
    text: str
    top_k: int = 5
    filter: Dict = Field(default_factory=dict)


class VectorResult(BaseModel):
    id: str
    content: str
    metadata: Dict
    score: float
