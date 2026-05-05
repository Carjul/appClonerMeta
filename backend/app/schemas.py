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
    copiesToCreate: Optional[int] = 49


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
    configId: str
    campaignIds: List[str]
    execute: bool = False
    minSpend: Optional[float] = 5.0
    targetBudget: Optional[float] = 1.0


class DailyReportRunRequest(BaseModel):
    configId: str
    periods: Optional[List[str]] = None


class RulesCondition(BaseModel):
    metric: str
    op: str
    val: float


class RulesCreateRequest(BaseModel):
    source: str = Field(pattern="^(preset|custom)$")
    presetId: Optional[str] = None
    customType: Optional[str] = None
    customAction: Optional[str] = None
    customHour: Optional[int] = None
    customMinute: Optional[int] = None
    customActionCondition: Optional[str] = None
    timeRange: Optional[str] = None
    checkFreq: Optional[str] = None
    conditions: Optional[List[RulesCondition]] = None
    accountId: str
    accountName: str
    campaignIds: List[str]
    customName: Optional[str] = None


class RulesToggleRequest(BaseModel):
    enabled: bool


class RulesBulkToggleRequest(BaseModel):
    ruleIds: List[str]
    action: str = Field(pattern="^(pause|activate)$")


class RulesBulkDeleteRequest(BaseModel):
    ruleIds: List[str]


class JobStartResponse(BaseModel):
    jobId: str
    status: str


class JobResultResponse(BaseModel):
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
