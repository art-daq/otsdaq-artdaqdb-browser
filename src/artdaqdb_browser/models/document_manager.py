"""
File: document_manager.py
Purpose: Document Manager for OTS document operations.
Category: Data
Author: ArtdaqDB Browser Team
Depends: None
Exports: DocumentManager
Complexity: High | Lines: 1162
"""

from typing import Any, Dict, List, Optional
from .document import (
    OTSDocument,
    ConfigurationAssignment,
    EntityAssignment,
    BookkeepingUpdate,
    Bookkeeping,
    Aliases,
    Origin,
    DocumentData,
)


class DocumentManager:

    @staticmethod
    def add_configuration(document: OTSDocument, config_name: str, timestamp: str) -> OTSDocument:
        new_config = ConfigurationAssignment(name=config_name, assigned=timestamp)
        event = BookkeepingUpdate(
            event="addConfiguration", timestamp=timestamp, value={"name": config_name, "assigned": timestamp}
        )
        new_configurations = list(document.configurations) + [new_config]
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"configurations": new_configurations, "bookkeeping": new_bookkeeping})

    @staticmethod
    def remove_configuration(document: OTSDocument, config_name: str, timestamp: str) -> OTSDocument:
        config_to_remove = None
        for config in document.configurations:
            if config.name == config_name:
                config_to_remove = config
                break
        if config_to_remove is None:
            raise ValueError(f"Configuration '{config_name}' not found in document")
        event = BookkeepingUpdate(
            event="removeConfiguration",
            timestamp=timestamp,
            value={"name": config_name, "assigned": config_to_remove.assigned, "removed": timestamp},
        )
        new_configurations = [c for c in document.configurations if c.name != config_name]
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"configurations": new_configurations, "bookkeeping": new_bookkeeping})

    @staticmethod
    def remove_all_configurations(document: OTSDocument, timestamp: str) -> OTSDocument:
        if not document.configurations:
            return document
        new_updates = list(document.bookkeeping.updates)
        for config in document.configurations:
            event = BookkeepingUpdate(
                event="removeConfiguration",
                timestamp=timestamp,
                value={"name": config.name, "assigned": config.assigned, "removed": timestamp},
            )
            new_updates.append(event)
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"configurations": [], "bookkeeping": new_bookkeeping})

    @staticmethod
    def has_configuration(document: OTSDocument, config_name: str) -> bool:
        return any((c.name == config_name for c in document.configurations))

    @staticmethod
    def get_configurations(document: OTSDocument) -> List[str]:
        return [c.name for c in document.configurations]

    @staticmethod
    def add_alias(document: OTSDocument, alias_name: str, timestamp: str) -> OTSDocument:
        new_alias = {"name": alias_name, "assigned": timestamp}
        event = BookkeepingUpdate(
            event="addAlias", timestamp=timestamp, value={"name": alias_name, "assigned": timestamp}
        )
        new_active = list(document.aliases.active) + [new_alias]
        new_aliases = Aliases(active=new_active, history=list(document.aliases.history))
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"aliases": new_aliases, "bookkeeping": new_bookkeeping})

    @staticmethod
    def remove_alias(document: OTSDocument, alias_name: str, timestamp: str) -> OTSDocument:
        alias_to_remove = None
        for alias in document.aliases.active:
            if alias.get("name") == alias_name:
                alias_to_remove = alias
                break
        if alias_to_remove is None:
            raise ValueError(f"Alias '{alias_name}' not found in active aliases")
        history_entry = {
            "name": alias_name,
            "assigned": alias_to_remove.get("assigned", timestamp),
            "removed": timestamp,
        }
        event = BookkeepingUpdate(
            event="removeAlias",
            timestamp=timestamp,
            value={"name": alias_name, "assigned": alias_to_remove.get("assigned", timestamp), "removed": timestamp},
        )
        new_active = [a for a in document.aliases.active if a.get("name") != alias_name]
        new_history = list(document.aliases.history) + [history_entry]
        new_aliases = Aliases(active=new_active, history=new_history)
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"aliases": new_aliases, "bookkeeping": new_bookkeeping})

    @staticmethod
    def has_alias(document: OTSDocument, alias_name: str) -> bool:
        return any((a.get("name") == alias_name for a in document.aliases.active))

    @staticmethod
    def get_active_aliases(document: OTSDocument) -> List[str]:
        return [a.get("name", "") for a in document.aliases.active]

    @staticmethod
    def get_alias_history(document: OTSDocument) -> List[Dict[str, Any]]:
        return list(document.aliases.history)

    @staticmethod
    def add_entity(document: OTSDocument, entity_name: str, timestamp: str) -> OTSDocument:
        new_entity = EntityAssignment(name=entity_name, assigned=timestamp)
        event = BookkeepingUpdate(
            event="addEntity", timestamp=timestamp, value={"name": entity_name, "assigned": timestamp}
        )
        new_entities = list(document.entities) + [new_entity]
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"entities": new_entities, "bookkeeping": new_bookkeeping})

    @staticmethod
    def remove_entity(document: OTSDocument, entity_name: str, timestamp: str) -> OTSDocument:
        entity_to_remove = None
        for entity in document.entities:
            if entity.name == entity_name:
                entity_to_remove = entity
                break
        if entity_to_remove is None:
            raise ValueError(f"Entity '{entity_name}' not found in document")
        event = BookkeepingUpdate(
            event="removeEntity",
            timestamp=timestamp,
            value={"name": entity_name, "assigned": entity_to_remove.assigned, "removed": timestamp},
        )
        new_entities = [e for e in document.entities if e.name != entity_name]
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"entities": new_entities, "bookkeeping": new_bookkeeping})

    @staticmethod
    def remove_all_entities(document: OTSDocument, timestamp: str) -> OTSDocument:
        if not document.entities:
            return document
        new_updates = list(document.bookkeeping.updates)
        for entity in document.entities:
            event = BookkeepingUpdate(
                event="removeEntity",
                timestamp=timestamp,
                value={"name": entity.name, "assigned": entity.assigned, "removed": timestamp},
            )
            new_updates.append(event)
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"entities": [], "bookkeeping": new_bookkeeping})

    @staticmethod
    def has_entity(document: OTSDocument, entity_name: str) -> bool:
        return any((e.name == entity_name for e in document.entities))

    @staticmethod
    def get_entities(document: OTSDocument) -> List[str]:
        return [e.name for e in document.entities]

    @staticmethod
    def add_run(document: OTSDocument, run_name: str, timestamp: str) -> OTSDocument:
        new_run = {"name": run_name, "assigned": timestamp}
        event = BookkeepingUpdate(event="addRun", timestamp=timestamp, value={"name": run_name, "assigned": timestamp})
        new_runs = list(document.runs) + [new_run]
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"runs": new_runs, "bookkeeping": new_bookkeeping})

    @staticmethod
    def has_run(document: OTSDocument, run_name: str) -> bool:
        return any((r.get("name") == run_name for r in document.runs))

    @staticmethod
    def get_runs(document: OTSDocument) -> List[str]:
        return [r.get("name", "") for r in document.runs]

    @staticmethod
    def mark_readonly(document: OTSDocument, timestamp: str, readonly: bool = True) -> OTSDocument:
        event_name = "markReadOnly" if readonly else "unmarkReadOnly"
        event = BookkeepingUpdate(event=event_name, timestamp=timestamp, value={"readonly": readonly})
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=readonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"bookkeeping": new_bookkeeping})

    @staticmethod
    def is_readonly(document: OTSDocument) -> bool:
        return document.bookkeeping.isreadonly

    @staticmethod
    def mark_deleted(document: OTSDocument, timestamp: str, deleted: bool = True) -> OTSDocument:
        event_name = "markDeleted" if deleted else "unmarkDeleted"
        event = BookkeepingUpdate(event=event_name, timestamp=timestamp, value={"deleted": deleted})
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=deleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"bookkeeping": new_bookkeeping})

    @staticmethod
    def is_deleted(document: OTSDocument) -> bool:
        return document.bookkeeping.isdeleted

    @staticmethod
    def is_readonly_or_deleted(document: OTSDocument) -> bool:
        return document.bookkeeping.isreadonly or document.bookkeeping.isdeleted

    @staticmethod
    def require_modifiable(document: OTSDocument) -> None:
        if DocumentManager.is_readonly_or_deleted(document):
            raise ValueError("Document is readonly or deleted and cannot be modified")

    @staticmethod
    def set_version(document: OTSDocument, version: str, timestamp: str) -> OTSDocument:
        if document.version == version:
            return document
        event = BookkeepingUpdate(
            event="setVersion", timestamp=timestamp, value={"name": version, "assigned": timestamp}
        )
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"version": version, "bookkeeping": new_bookkeeping})

    @staticmethod
    def get_version(document: OTSDocument) -> str:
        return document.version

    @staticmethod
    def set_collection(document: OTSDocument, collection: str, timestamp: str) -> OTSDocument:
        if document.collection == collection:
            return document
        event = BookkeepingUpdate(
            event="setCollection", timestamp=timestamp, value={"name": collection, "assigned": timestamp}
        )
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"collection": collection, "bookkeeping": new_bookkeeping})

    @staticmethod
    def get_collection(document: OTSDocument) -> str:
        return document.collection

    @staticmethod
    def set_configuration_type(document: OTSDocument, config_type: str, timestamp: str) -> OTSDocument:
        if document.configtype == config_type:
            return document
        event = BookkeepingUpdate(
            event="setConfigurationType", timestamp=timestamp, value={"name": config_type, "assigned": timestamp}
        )
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"configtype": config_type, "bookkeeping": new_bookkeeping})

    @staticmethod
    def get_configuration_type(document: OTSDocument) -> str:
        return document.configtype

    @staticmethod
    def add_comment(document: OTSDocument, text: str, linenum: int, timestamp: str) -> OTSDocument:
        new_comment = {"linenum": linenum, "text": text}
        event = BookkeepingUpdate(event="addComment", timestamp=timestamp, value={"linenum": linenum, "text": text})
        new_comments = list(document.comments) + [new_comment]
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"comments": new_comments, "bookkeeping": new_bookkeeping})

    @staticmethod
    def remove_comment(document: OTSDocument, linenum: int, timestamp: str) -> OTSDocument:
        comment_to_remove = None
        for comment in document.comments:
            if comment.get("linenum") == linenum:
                comment_to_remove = comment
                break
        if comment_to_remove is None:
            raise ValueError(f"Comment at line {linenum} not found in document")
        event = BookkeepingUpdate(
            event="removeComment",
            timestamp=timestamp,
            value={"linenum": linenum, "text": comment_to_remove.get("text", "")},
        )
        new_comments = [c for c in document.comments if c.get("linenum") != linenum]
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"comments": new_comments, "bookkeeping": new_bookkeeping})

    @staticmethod
    def get_comments(document: OTSDocument) -> List[Dict[str, Any]]:
        return list(document.comments)

    @staticmethod
    def has_comment_at_line(document: OTSDocument, linenum: int) -> bool:
        return any((c.get("linenum") == linenum for c in document.comments))

    @staticmethod
    def set_changelog(document: OTSDocument, changelog: str, timestamp: str) -> OTSDocument:
        event = BookkeepingUpdate(event="setChangelog", timestamp=timestamp, value={"changelog": changelog})
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"changelog": changelog, "bookkeeping": new_bookkeeping})

    @staticmethod
    def get_changelog(document: OTSDocument) -> str:
        return document.changelog

    @staticmethod
    def append_changelog(document: OTSDocument, entry: str, timestamp: str) -> OTSDocument:
        if document.changelog and document.changelog != "notprovided":
            new_changelog = f"{document.changelog}\n{entry}"
        else:
            new_changelog = entry
        return DocumentManager.set_changelog(document, new_changelog, timestamp)

    @staticmethod
    def set_origin(document: OTSDocument, source: str, name: str, format: str, timestamp: str) -> OTSDocument:
        new_origin = Origin(
            source=source, name=name, format=format, created=timestamp, rawdata=list(document.origin.rawdata)
        )
        event = BookkeepingUpdate(
            event="setOrigin", timestamp=timestamp, value={"source": source, "name": name, "format": format}
        )
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"origin": new_origin, "bookkeeping": new_bookkeeping})

    @staticmethod
    def get_origin(document: OTSDocument) -> Dict[str, Any]:
        return document.origin.model_dump()

    @staticmethod
    def set_data(document: OTSDocument, data: Dict[str, Any]) -> OTSDocument:
        new_document_data = DocumentData(
            data=data, metadata=dict(document.document.metadata), search=list(document.document.search)
        )
        return document.model_copy(update={"document": new_document_data})

    @staticmethod
    def get_data(document: OTSDocument) -> Dict[str, Any]:
        return document.document.data

    @staticmethod
    def set_metadata(document: OTSDocument, metadata: Dict[str, Any]) -> OTSDocument:
        new_document_data = DocumentData(
            data=dict(document.document.data), metadata=metadata, search=list(document.document.search)
        )
        return document.model_copy(update={"document": new_document_data})

    @staticmethod
    def get_metadata(document: OTSDocument) -> Dict[str, Any]:
        return document.document.metadata

    @staticmethod
    def set_search(document: OTSDocument, search: List[Any]) -> OTSDocument:
        new_document_data = DocumentData(
            data=dict(document.document.data), metadata=dict(document.document.metadata), search=search
        )
        return document.model_copy(update={"document": new_document_data})

    @staticmethod
    def get_search(document: OTSDocument) -> List[Any]:
        return document.document.search

    @staticmethod
    def add_attachment(
        document: OTSDocument, name: str, timestamp: str, mime_type: str = "", size: int = 0
    ) -> OTSDocument:
        new_attachment = {"name": name, "type": mime_type, "size": size, "created": timestamp}
        event = BookkeepingUpdate(
            event="addAttachment", timestamp=timestamp, value={"name": name, "type": mime_type, "size": size}
        )
        new_attachments = list(document.attachments) + [new_attachment]
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"attachments": new_attachments, "bookkeeping": new_bookkeeping})

    @staticmethod
    def remove_attachment(document: OTSDocument, name: str, timestamp: str) -> OTSDocument:
        attachment_to_remove = None
        for attachment in document.attachments:
            if attachment.get("name") == name:
                attachment_to_remove = attachment
                break
        if attachment_to_remove is None:
            raise ValueError(f"Attachment '{name}' not found in document")
        event = BookkeepingUpdate(event="removeAttachment", timestamp=timestamp, value={"name": name})
        new_attachments = [a for a in document.attachments if a.get("name") != name]
        new_updates = list(document.bookkeeping.updates) + [event]
        new_bookkeeping = Bookkeeping(
            isdeleted=document.bookkeeping.isdeleted,
            isreadonly=document.bookkeeping.isreadonly,
            updates=new_updates,
            created=document.bookkeeping.created,
        )
        return document.model_copy(update={"attachments": new_attachments, "bookkeeping": new_bookkeeping})

    @staticmethod
    def get_attachments(document: OTSDocument) -> List[Dict[str, Any]]:
        return list(document.attachments)

    @staticmethod
    def has_attachment(document: OTSDocument, name: str) -> bool:
        return any((a.get("name") == name for a in document.attachments))

    @staticmethod
    def get_updates(document: OTSDocument) -> List[Dict[str, Any]]:
        return [u.model_dump() for u in document.bookkeeping.updates]

    @staticmethod
    def get_created_timestamp(document: OTSDocument) -> str:
        return document.bookkeeping.created

    @staticmethod
    def get_update_count(document: OTSDocument) -> int:
        return len(document.bookkeeping.updates)

    @staticmethod
    def get_updates_by_event(document: OTSDocument, event_type: str) -> List[Dict[str, Any]]:
        return [u.model_dump() for u in document.bookkeeping.updates if u.event == event_type]
