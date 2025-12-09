"""
File: exceptions.py
Purpose: Custom exceptions for OTS Browser application.
Category: Utility
Author: ArtdaqDB Browser Team
Depends: None
Exports: OTSBrowserError, DataError, BackendError, DocumentNotFoundError, CollectionNotFoundError, ...
Complexity: Medium | Lines: 175
"""

from typing import Optional


class OTSBrowserError(Exception):

    def __init__(self, message: str, details: Optional[str] = None):
        self.message = message
        self.details = details
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message}: {self.details}"
        return self.message


class DataError(OTSBrowserError):
    pass


class BackendError(DataError):
    pass


class DocumentNotFoundError(DataError):

    def __init__(self, document_id: str):
        super().__init__(f"Document not found", details=f"ID: {document_id}")
        self.document_id = document_id


class CollectionNotFoundError(DataError):

    def __init__(self, collection_name: str):
        super().__init__(f"Collection not found", details=f"Name: {collection_name}")
        self.collection_name = collection_name


class ConfigurationNotFoundError(DataError):

    def __init__(self, config_name: str):
        super().__init__(f"Configuration not found", details=f"Name: {config_name}")
        self.config_name = config_name


class DocumentLoadError(DataError):

    def __init__(self, source: str, original_error: Optional[Exception] = None):
        details = str(original_error) if original_error else None
        super().__init__(f"Failed to load document from {source}", details=details)
        self.source = source
        self.original_error = original_error


class DocumentSaveError(DataError):

    def __init__(self, document_id: str, original_error: Optional[Exception] = None):
        details = str(original_error) if original_error else None
        super().__init__(f"Failed to save document {document_id}", details=details)
        self.document_id = document_id
        self.original_error = original_error


class DocumentDeleteError(DataError):

    def __init__(self, document_id: str, original_error: Optional[Exception] = None):
        details = str(original_error) if original_error else None
        super().__init__(f"Failed to delete document {document_id}", details=details)
        self.document_id = document_id
        self.original_error = original_error


class CacheError(OTSBrowserError):
    pass


class CacheReadError(CacheError):

    def __init__(self, key: str, original_error: Optional[Exception] = None):
        details = str(original_error) if original_error else None
        super().__init__(f"Failed to read cache key '{key}'", details=details)
        self.key = key
        self.original_error = original_error


class CacheWriteError(CacheError):

    def __init__(self, key: str, original_error: Optional[Exception] = None):
        details = str(original_error) if original_error else None
        super().__init__(f"Failed to write cache key '{key}'", details=details)
        self.key = key
        self.original_error = original_error


class ValidationError(OTSBrowserError):
    pass


class InvalidDocumentError(ValidationError):

    def __init__(self, field: str, reason: str):
        super().__init__(f"Invalid document: {field}", details=reason)
        self.field = field
        self.reason = reason


class InvalidConfigurationNameError(ValidationError):

    def __init__(self, name: str, expected_pattern: str = "<SystemName>_v<number>"):
        super().__init__(f"Invalid configuration name: '{name}'", details=f"Expected pattern: {expected_pattern}")
        self.name = name
        self.expected_pattern = expected_pattern


class NavigationError(OTSBrowserError):
    pass


class NoSelectionError(NavigationError):

    def __init__(self, item_type: str):
        super().__init__(f"No {item_type} selected")
        self.item_type = item_type
