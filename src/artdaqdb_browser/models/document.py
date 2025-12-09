"""
File: document.py
Purpose: Pydantic models for OTS document schema.
Category: Data
Author: ArtdaqDB Browser Team
Depends: pydantic
Exports: ConfigurationAssignment, EntityAssignment, RunAssignment, AliasEntry, AliasHistoryEntry, ...
Complexity: High | Lines: 396
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class ConfigurationAssignment(BaseModel):
    name: str
    assigned: str


class EntityAssignment(BaseModel):
    name: str
    assigned: str


class RunAssignment(BaseModel):
    name: str
    assigned: str


class AliasEntry(BaseModel):
    name: str
    assigned: str


class AliasHistoryEntry(BaseModel):
    name: str
    assigned: str
    removed: str


class Aliases(BaseModel):
    active: List[Dict[str, Any]] = Field(default_factory=list)
    history: List[Dict[str, Any]] = Field(default_factory=list)


class Comment(BaseModel):
    linenum: int
    text: str


class Attachment(BaseModel):
    name: str
    type: str = ""
    size: int = 0
    created: str = ""


class BookkeepingUpdate(BaseModel):
    event: str
    timestamp: str
    value: Dict[str, Any]


class Bookkeeping(BaseModel):
    isdeleted: bool = False
    isreadonly: bool = False
    updates: List[BookkeepingUpdate] = Field(default_factory=list)
    created: str


class Origin(BaseModel):
    source: str
    name: str
    format: str
    created: str
    rawdata: List[Any] = Field(default_factory=list)


class DocumentData(BaseModel):
    data: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    search: List[Any] = Field(default_factory=list)


class OTSDocument(BaseModel):
    id: str = Field(alias="_id")
    collection: str
    version: str
    configtype: str
    document: DocumentData
    changelog: str
    origin: Origin
    bookkeeping: Bookkeeping
    configurations: List[ConfigurationAssignment] = Field(default_factory=list)
    entities: List[EntityAssignment] = Field(default_factory=list)
    aliases: Aliases = Field(default_factory=Aliases)
    runs: List[Dict[str, Any]] = Field(default_factory=list)
    comments: List[Dict[str, Any]] = Field(default_factory=list)
    attachments: List[Dict[str, Any]] = Field(default_factory=list)
    model_config = {"populate_by_name": True}

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        if not v or len(v) != 24:
            raise ValueError("Document ID must be a 24-character string")
        try:
            int(v, 16)
        except ValueError:
            raise ValueError("Document ID must be a valid hexadecimal string")
        return v

    def get_latest_assignment(self) -> Optional[ConfigurationAssignment]:
        if not self.configurations:
            return None
        return max(self.configurations, key=lambda c: c.assigned)

    def is_in_configuration(self, config_name: str) -> bool:
        return any((c.name == config_name for c in self.configurations))

    def get_configuration_names(self) -> List[str]:
        return [c.name for c in self.configurations]

    def get_entity_names(self) -> List[str]:
        return [e.name for e in self.entities]

    def has_entity(self, entity_name: str) -> bool:
        return any((e.name == entity_name for e in self.entities))

    def get_active_alias_names(self) -> List[str]:
        return [a.get("name", "") for a in self.aliases.active]

    def has_alias(self, alias_name: str) -> bool:
        return any((a.get("name") == alias_name for a in self.aliases.active))

    def get_run_names(self) -> List[str]:
        return [r.get("name", "") for r in self.runs]

    def has_run(self, run_name: str) -> bool:
        return any((r.get("name") == run_name for r in self.runs))

    def is_readonly(self) -> bool:
        return self.bookkeeping.isreadonly

    def is_deleted(self) -> bool:
        return self.bookkeeping.isdeleted

    def is_readonly_or_deleted(self) -> bool:
        return self.bookkeeping.isreadonly or self.bookkeeping.isdeleted


class ConfigurationSummaryInfo(BaseModel):
    name: str
    assigned: Optional[str] = None


class CollectionInfo(BaseModel):
    name: str
    version_count: int
    latest_version: Optional[str] = None
    last_updated: Optional[str] = None


class ConfigurationInfo(BaseModel):
    name: str
    collection_count: int
    last_assigned: str
    collections: List[str] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    id: str
    collection: str
    version: str
    created: Optional[str] = None
    is_deleted: bool = False
    is_readonly: bool = False
    config_assignments: List[ConfigurationSummaryInfo] = Field(default_factory=list)

    def is_readonly_or_deleted(self) -> bool:
        return self.is_readonly or self.is_deleted

    def get_assigned_for_config(self, config_name: str) -> Optional[str]:
        for cfg in self.config_assignments:
            if cfg.name == config_name:
                return cfg.assigned
        return None


class VersionSummary(BaseModel):
    id: str
    version: str
    created: Optional[str] = None
    config_count: int = 0
    is_deleted: bool = False
    is_readonly: bool = False

    def is_readonly_or_deleted(self) -> bool:
        return self.is_readonly or self.is_deleted
