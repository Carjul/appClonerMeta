from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ConfigCreate(BaseModel):
    name: str = Field(min_length=1)
    bmId: str = Field(min_length=1)
    accessToken: str = Field(min_length=1)


class ConfigUpdate(BaseModel):
    name: Optional[str] = None
    bmId: Optional[str] = None
    accessToken: Optional[str] = None


class ExplorerRunRequest(BaseModel):
    configId: str


class BulkCloneRequest(BaseModel):
    configId: str
    campaignId: str


class SingleCloneRequest(BaseModel):
    configId: str
    campaignIds: List[str]


class DeleteCampaignsRequest(BaseModel):
    configId: str
    campaignIds: List[str]
    batch: Optional[int] = 10


class CampaignStatusRequest(BaseModel):
    configId: str
    campaignIds: List[str]
    status: str = Field(pattern="^(ACTIVE|PAUSED)$")
    apiVersion: Optional[str] = "v21.0"


class ReduceBudgetsRequest(BaseModel):
    tokenConfigIdBm1: Optional[str] = None
    tokenConfigIdBm2: Optional[str] = None
    execute: bool = False
    minSpend: Optional[float] = 5.0
    targetBudget: Optional[float] = 1.0


class JobStartResponse(BaseModel):
    jobId: str
    status: str


class JobResultResponse(BaseModel):
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
