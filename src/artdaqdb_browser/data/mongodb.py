"""
File: mongodb.py
Purpose: MongoDB backend for reading documents from a MongoDB database.
Category: Data
Author: ArtdaqDB Browser Team
Depends: pymongo
Exports: MongoDBBackend
Complexity: High | Lines: 1892
"""

from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient, UpdateOne, DeleteOne
from pymongo.errors import ConnectionFailure, OperationFailure, BulkWriteError
from ..models import (
    OTSDocument,
    ConfigurationInfo,
    ConfigurationSummaryInfo,
    CollectionInfo,
    DocumentSummary,
    VersionSummary,
)
from ..config import ConfigLoader, AppConfig, parse_mongodb_uri
from ..trace import trace
from .base import DataBackend, BatchOperationResult


class MongoDBBackend(DataBackend):

    def __init__(self, config: Optional[AppConfig] = None):
        if config is None:
            loader = ConfigLoader()
            (config, _) = loader.load()
        self.config = config
        self._client: Optional[MongoClient] = None
        self._db = None
        self._documents: Optional[List[OTSDocument]] = None
        self._documents_by_id: Optional[Dict[str, OTSDocument]] = None
        self._connect()

    def _connect(self) -> None:
        mongo_config = self.config.data_source.mongodb
        auth_config = self.config.mongodb_auth
        (host, port, uri_database) = parse_mongodb_uri(mongo_config.uri)
        database = mongo_config.database or uri_database
        trace.info(
            "Connecting to MongoDB server",
            tags=["database", "lifecycle"],
            host=host,
            port=port,
            database=database,
            auth_type=auth_config.type,
        )
        options = {
            "connectTimeoutMS": mongo_config.connect_timeout_ms,
            "serverSelectionTimeoutMS": mongo_config.server_selection_timeout_ms,
            "directConnection": mongo_config.direct_connection,
        }
        if mongo_config.socket_timeout_ms > 0:
            options["socketTimeoutMS"] = mongo_config.socket_timeout_ms
        if auth_config.type == "none":
            uri = f"mongodb://{host}:{port}/"
            self._client = MongoClient(uri, **options)
        elif auth_config.type == "x509":
            x509 = auth_config.x509
            cert_dir = x509.get_cert_dir_path()
            ca_cert = cert_dir / x509.ca_cert
            client_cert = cert_dir / x509.client_cert
            uri = f"mongodb://{host}:{port}/"
            options.update(
                {
                    "tls": True,
                    "tlsCAFile": str(ca_cert),
                    "tlsCertificateKeyFile": str(client_cert),
                    "authMechanism": x509.auth_mechanism,
                    "authSource": x509.auth_source,
                }
            )
            if x509.allow_invalid_certificates:
                options["tlsAllowInvalidCertificates"] = True
            if x509.allow_invalid_hostnames:
                options["tlsAllowInvalidHostnames"] = True
            self._client = MongoClient(uri, **options)
        elif auth_config.type == "userpass":
            userpass = auth_config.userpass
            uri = f"mongodb://{host}:{port}/"
            options.update(
                {"username": userpass.user, "password": userpass.password, "authSource": userpass.auth_source}
            )
            if userpass.auth_mechanism != "DEFAULT":
                options["authMechanism"] = userpass.auth_mechanism
            self._client = MongoClient(uri, **options)
        else:
            raise ValueError(f"Unsupported authentication type: {auth_config.type}")
        self._db = self._client[database]
        try:
            self._client.admin.command("ping")
            trace.info("MongoDB connection established successfully", tags=["database", "lifecycle"], database=database)
        except ConnectionFailure as e:
            trace.error(
                "MongoDB connection failed - unable to reach server",
                tags=["database", "lifecycle", "error"],
                exception=e,
                host=host,
                port=port,
            )
            raise

    def _load_all_documents(self) -> None:
        if self._documents is not None:
            trace.trace(
                "Documents already cached, skipping load", tags=["database", "cache"], cached_count=len(self._documents)
            )
            return
        trace.info("Loading all documents from MongoDB into memory", tags=["database", "query"])
        documents = []
        documents_by_id = {}
        collection_names = self._db.list_collection_names()
        for collection_name in collection_names:
            if collection_name.startswith("system."):
                continue
            try:
                collection = self._db[collection_name]
                max_items = self.config.ui.max_list_items
                for doc_data in collection.find().limit(max_items):
                    try:
                        if "_id" in doc_data:
                            doc_data["_id"] = str(doc_data["_id"])
                        doc = OTSDocument(**doc_data)
                        documents.append(doc)
                        documents_by_id[doc.id] = doc
                    except Exception as e:
                        trace.warn(
                            "Failed to parse document from MongoDB",
                            tags=["database", "error"],
                            collection=collection_name,
                            error=str(e),
                        )
                        continue
            except Exception as e:
                trace.error(
                    "Failed to load collection from MongoDB",
                    tags=["database", "error"],
                    exception=e,
                    collection=collection_name,
                )
                continue
        self._documents = documents
        self._documents_by_id = documents_by_id
        trace.info(
            "All documents loaded from MongoDB",
            tags=["database", "query"],
            document_count=len(documents),
            collections_processed=len(collection_names),
        )

    def get_document_by_id(self, document_id: str) -> Optional[OTSDocument]:
        self._load_all_documents()
        return self._documents_by_id.get(document_id)

    def get_all_documents(self) -> List[OTSDocument]:
        self._load_all_documents()
        return self._documents.copy()

    def get_documents_by_collection(self, collection_name: str) -> List[OTSDocument]:
        self._load_all_documents()
        return [doc for doc in self._documents if doc.collection == collection_name]

    def get_documents_by_configuration(self, config_name: str) -> List[OTSDocument]:
        self._load_all_documents()
        return [doc for doc in self._documents if doc.is_in_configuration(config_name)]

    def get_document_versions(self, collection_name: str) -> List[OTSDocument]:
        docs = self.get_documents_by_collection(collection_name)
        return sorted(docs, key=lambda d: int(d.version) if d.version.isdigit() else 0)

    def list_configurations(self) -> List[str]:
        self._load_all_documents()
        configs = set()
        for doc in self._documents:
            configs.update(doc.get_configuration_names())
        return sorted(configs)

    def list_collections(self) -> List[str]:
        self._load_all_documents()
        collections = set((doc.collection for doc in self._documents))
        return sorted(collections)

    def get_configuration_info(self) -> List[ConfigurationInfo]:
        self._load_all_documents()
        config_data: Dict[str, Dict] = defaultdict(lambda: {"collections": set(), "last_assigned": ""})
        for doc in self._documents:
            for config in doc.configurations:
                config_name = config.name
                config_data[config_name]["collections"].add(doc.collection)
                current_last = config_data[config_name]["last_assigned"]
                if not current_last or config.assigned > current_last:
                    config_data[config_name]["last_assigned"] = config.assigned
        result = []
        for config_name, data in config_data.items():
            result.append(
                ConfigurationInfo(
                    name=config_name,
                    collection_count=len(data["collections"]),
                    last_assigned=data["last_assigned"],
                    collections=sorted(data["collections"]),
                )
            )
        result.sort(key=lambda c: c.last_assigned, reverse=True)
        return result

    def get_collection_info(self) -> List[CollectionInfo]:
        self._load_all_documents()
        collection_data: Dict[str, List[OTSDocument]] = defaultdict(list)
        for doc in self._documents:
            collection_data[doc.collection].append(doc)
        result = []
        for collection_name, docs in collection_data.items():
            sorted_docs = sorted(docs, key=lambda d: int(d.version) if d.version.isdigit() else 0, reverse=True)
            latest_doc = sorted_docs[0] if sorted_docs else None
            result.append(
                CollectionInfo(
                    name=collection_name,
                    version_count=len(docs),
                    latest_version=latest_doc.version if latest_doc else None,
                    last_updated=latest_doc.bookkeeping.created if latest_doc else None,
                )
            )
        result.sort(key=lambda c: c.name)
        return result

    def update_document(self, document: OTSDocument) -> bool:
        try:
            collection = self._db[document.collection]
            doc_dict = document.model_dump(by_alias=True)
            doc_dict["_id"] = ObjectId(document.id)
            result = collection.replace_one({"_id": ObjectId(document.id)}, doc_dict, upsert=True)
            if self._documents is not None:
                for i, doc in enumerate(self._documents):
                    if doc.id == document.id:
                        self._documents[i] = document
                        break
                else:
                    self._documents.append(document)
                self._documents_by_id[document.id] = document
            bookkeeping_updates = doc_dict.get("bookkeeping", {}).get("updates", [])
            trace.info(
                "Document updated in MongoDB",
                tags=["database", "mutation"],
                document_id=document.id,
                collection=document.collection,
                modified_count=result.modified_count,
                bookkeeping_updates_count=len(bookkeeping_updates),
            )
            return True
        except Exception as e:
            trace.error(
                "Failed to update document in MongoDB",
                tags=["database", "mutation", "error"],
                exception=e,
                document_id=document.id,
            )
            return False

    def delete_document(self, document_id: str, soft_delete: bool = True) -> bool:
        trace.debug(
            "Delete document requested", tags=["database", "mutation"], document_id=document_id, soft_delete=soft_delete
        )
        try:
            doc = self.get_document_by_id_direct(document_id)
            if not doc:
                trace.warn("Delete failed: document not found", tags=["database", "mutation"], document_id=document_id)
                return False
            if soft_delete:
                self._apply_soft_delete(doc)
                return self.update_document(doc)
            else:
                collection = self._db[doc.collection]
                result = collection.delete_one({"_id": ObjectId(document_id)})
                if self._documents is not None:
                    self._documents = [d for d in self._documents if d.id != document_id]
                    if document_id in self._documents_by_id:
                        del self._documents_by_id[document_id]
                trace.info(
                    "Document permanently deleted from MongoDB",
                    tags=["database", "mutation"],
                    document_id=document_id,
                    collection=doc.collection,
                    deleted_count=result.deleted_count,
                )
                return result.deleted_count > 0
        except Exception as e:
            trace.error(
                "Failed to delete document from MongoDB",
                tags=["database", "mutation", "error"],
                exception=e,
                document_id=document_id,
                soft_delete=soft_delete,
            )
            return False

    def assign_configuration(self, document_id: str, config_name: str, timestamp: str) -> bool:
        trace.debug(
            "Assigning configuration to document",
            tags=["database", "mutation"],
            document_id=document_id,
            config_name=config_name,
        )
        try:
            doc = self.get_document_by_id_direct(document_id)
            if not doc:
                trace.warn(
                    "Configuration assignment failed: document not found",
                    tags=["database", "mutation"],
                    document_id=document_id,
                    config_name=config_name,
                )
                return False
            self._apply_configuration_assignment(doc, config_name, timestamp)
            success = self.update_document(doc)
            if success:
                trace.info(
                    "Configuration assigned to document successfully",
                    tags=["database", "mutation"],
                    document_id=document_id,
                    config_name=config_name,
                    collection=doc.collection,
                )
            return success
        except Exception as e:
            trace.error(
                "Failed to assign configuration to document",
                tags=["database", "mutation", "error"],
                exception=e,
                document_id=document_id,
                config_name=config_name,
            )
            return False

    def remove_configuration_assignment(self, document_id: str, config_name: str, timestamp: str) -> bool:
        trace.debug(
            "Removing configuration from document",
            tags=["database", "mutation"],
            document_id=document_id,
            config_name=config_name,
        )
        try:
            doc = self.get_document_by_id_direct(document_id)
            if not doc:
                trace.warn(
                    "Configuration removal failed: document not found",
                    tags=["database", "mutation"],
                    document_id=document_id,
                    config_name=config_name,
                )
                return False
            (success_removal, original_assigned) = self._apply_configuration_removal(doc, config_name, timestamp)
            if not success_removal:
                trace.warn(
                    "Configuration removal failed: configuration not found in document",
                    tags=["database", "mutation"],
                    document_id=document_id,
                    config_name=config_name,
                )
                return False
            success = self.update_document(doc)
            if success:
                trace.info(
                    "Configuration removed from document successfully",
                    tags=["database", "mutation"],
                    document_id=document_id,
                    config_name=config_name,
                    collection=doc.collection,
                    original_assigned=original_assigned,
                )
            return success
        except Exception as e:
            trace.error(
                "Failed to remove configuration from document",
                tags=["database", "mutation", "error"],
                exception=e,
                document_id=document_id,
                config_name=config_name,
            )
            return False

    def get_documents_by_configuration_summary(self, config_name: str) -> List[DocumentSummary]:
        trace.debug(
            "Fetching document summaries for configuration (optimized with assigned)",
            tags=["database", "query"],
            config_name=config_name,
        )
        results = []
        collection_names = self._db.list_collection_names()
        pipeline = [
            {"$match": {"configurations.name": config_name}},
            {
                "$project": {
                    "_id": 1,
                    "collection": 1,
                    "version": 1,
                    "created": "$bookkeeping.created",
                    "is_deleted": {"$ifNull": ["$bookkeeping.isdeleted", False]},
                    "is_readonly": {"$ifNull": ["$bookkeeping.isreadonly", False]},
                    "config_assignment": {
                        "$filter": {
                            "input": "$configurations",
                            "as": "cfg",
                            "cond": {"$eq": ["$$cfg.name", config_name]},
                        }
                    },
                }
            },
        ]
        for collection_name in collection_names:
            if collection_name.startswith("system."):
                continue
            try:
                collection = self._db[collection_name]
                for doc in collection.aggregate(pipeline):
                    config_assignments = []
                    config_array = doc.get("config_assignment", [])
                    for cfg in config_array:
                        config_assignments.append(
                            ConfigurationSummaryInfo(name=cfg.get("name", config_name), assigned=cfg.get("assigned"))
                        )
                    results.append(
                        DocumentSummary(
                            id=str(doc["_id"]),
                            collection=doc.get("collection", collection_name),
                            version=doc.get("version", "0"),
                            created=doc.get("created"),
                            is_deleted=doc.get("is_deleted", False),
                            is_readonly=doc.get("is_readonly", False),
                            config_assignments=config_assignments,
                        )
                    )
            except Exception as e:
                trace.warn(
                    "Error querying collection for configuration summaries",
                    tags=["database", "query", "error"],
                    collection=collection_name,
                    error=str(e),
                )
                continue
        trace.debug(
            "Document summaries retrieved for configuration",
            tags=["database", "query"],
            config_name=config_name,
            result_count=len(results),
        )
        return results

    def get_documents_by_configurations_summary_batch(
        self, config_names: List[str]
    ) -> Dict[str, List[DocumentSummary]]:
        if not config_names:
            return {}
        config_names_set = set(config_names)
        trace.info(
            "Fetching document summaries for configurations (batch)",
            tags=["database", "query", "batch"],
            config_count=len(config_names),
        )
        results: Dict[str, List[DocumentSummary]] = defaultdict(list)
        collection_names = [name for name in self._db.list_collection_names() if not name.startswith("system.")]
        pipeline = [
            {"$match": {"configurations.name": {"$in": list(config_names_set)}}},
            {
                "$project": {
                    "_id": 1,
                    "collection": 1,
                    "version": 1,
                    "created": "$bookkeeping.created",
                    "is_deleted": {"$ifNull": ["$bookkeeping.isdeleted", False]},
                    "is_readonly": {"$ifNull": ["$bookkeeping.isreadonly", False]},
                    "config_assignments": {
                        "$filter": {
                            "input": "$configurations",
                            "as": "cfg",
                            "cond": {"$in": ["$$cfg.name", list(config_names_set)]},
                        }
                    },
                }
            },
        ]

        def process_collection(coll_name: str) -> List[Tuple[str, DocumentSummary]]:
            pairs = []
            try:
                collection = self._db[coll_name]
                for doc in collection.aggregate(pipeline):
                    doc_id = str(doc["_id"])
                    doc_collection = doc.get("collection", coll_name)
                    version = doc.get("version", "0")
                    created = doc.get("created")
                    is_deleted = doc.get("is_deleted", False)
                    is_readonly = doc.get("is_readonly", False)
                    config_array = doc.get("config_assignments", [])
                    for cfg in config_array:
                        cfg_name = cfg.get("name")
                        if cfg_name not in config_names_set:
                            continue
                        config_assignments = [ConfigurationSummaryInfo(name=cfg_name, assigned=cfg.get("assigned"))]
                        summary = DocumentSummary(
                            id=doc_id,
                            collection=doc_collection,
                            version=version,
                            created=created,
                            is_deleted=is_deleted,
                            is_readonly=is_readonly,
                            config_assignments=config_assignments,
                        )
                        pairs.append((cfg_name, summary))
            except Exception as e:
                trace.warn(
                    "Error querying collection for batch configuration summaries",
                    tags=["database", "query", "error", "batch"],
                    collection=coll_name,
                    error=str(e),
                )
            return pairs

        max_workers = min(len(collection_names), 8) if collection_names else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_collection, coll_name): coll_name for coll_name in collection_names}
            for future in as_completed(futures):
                pairs = future.result()
                for cfg_name, summary in pairs:
                    results[cfg_name].append(summary)
        total_docs = sum((len(docs) for docs in results.values()))
        trace.info(
            "Batch document summaries retrieved",
            tags=["database", "query", "batch"],
            config_count=len(config_names),
            configs_with_docs=len(results),
            total_documents=total_docs,
        )
        return dict(results)

    def get_document_versions_summary(self, collection_name: str) -> List[VersionSummary]:
        trace.debug(
            "Fetching version summaries for collection (optimized)",
            tags=["database", "query"],
            collection=collection_name,
        )
        results = []
        try:
            collection = self._db[collection_name]
            pipeline = [
                {
                    "$project": {
                        "_id": 1,
                        "version": 1,
                        "created": "$bookkeeping.created",
                        "is_deleted": {"$ifNull": ["$bookkeeping.isdeleted", False]},
                        "is_readonly": {"$ifNull": ["$bookkeeping.isreadonly", False]},
                        "config_count": {"$size": {"$ifNull": ["$configurations", []]}},
                    }
                }
            ]
            for doc in collection.aggregate(pipeline):
                results.append(
                    VersionSummary(
                        id=str(doc["_id"]),
                        version=doc.get("version", "0"),
                        created=doc.get("created"),
                        config_count=doc.get("config_count", 0),
                        is_deleted=doc.get("is_deleted", False),
                        is_readonly=doc.get("is_readonly", False),
                    )
                )
            results.sort(key=lambda x: int(x.version) if x.version.isdigit() else 0, reverse=True)
        except Exception as e:
            trace.error(
                "Failed to fetch version summaries from collection",
                tags=["database", "query", "error"],
                exception=e,
                collection=collection_name,
            )
        trace.debug(
            "Version summaries retrieved for collection",
            tags=["database", "query"],
            collection=collection_name,
            result_count=len(results),
        )
        return results

    def get_document_versions_summary_batch(self, collection_names: List[str]) -> Dict[str, List[VersionSummary]]:
        if not collection_names:
            return {}
        trace.info(
            "Fetching version summaries for collections (parallel batch)",
            tags=["database", "query", "batch"],
            collection_count=len(collection_names),
        )
        results: Dict[str, List[VersionSummary]] = {}
        pipeline = [
            {
                "$project": {
                    "_id": 1,
                    "version": 1,
                    "created": "$bookkeeping.created",
                    "is_deleted": {"$ifNull": ["$bookkeeping.isdeleted", False]},
                    "is_readonly": {"$ifNull": ["$bookkeeping.isreadonly", False]},
                    "config_count": {"$size": {"$ifNull": ["$configurations", []]}},
                }
            }
        ]

        def process_collection(coll_name: str) -> Tuple[str, List[VersionSummary]]:
            summaries = []
            try:
                collection = self._db[coll_name]
                for doc in collection.aggregate(pipeline):
                    summaries.append(
                        VersionSummary(
                            id=str(doc["_id"]),
                            version=doc.get("version", "0"),
                            created=doc.get("created"),
                            config_count=doc.get("config_count", 0),
                            is_deleted=doc.get("is_deleted", False),
                            is_readonly=doc.get("is_readonly", False),
                        )
                    )
                summaries.sort(key=lambda x: int(x.version) if x.version.isdigit() else 0, reverse=True)
            except Exception as e:
                trace.warn(
                    "Error fetching version summaries for collection",
                    tags=["database", "query", "error", "batch"],
                    collection=coll_name,
                    error=str(e),
                )
            return (coll_name, summaries)

        max_workers = min(len(collection_names), 8)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_collection, coll_name): coll_name for coll_name in collection_names}
            for future in as_completed(futures):
                (coll_name, summaries) = future.result()
                if summaries:
                    results[coll_name] = summaries
        total_versions = sum((len(v) for v in results.values()))
        trace.info(
            "Batch version summaries retrieved",
            tags=["database", "query", "batch"],
            collection_count=len(collection_names),
            collections_with_versions=len(results),
            total_versions=total_versions,
        )
        return results

    def list_configurations_optimized(self) -> List[str]:
        trace.debug("Fetching unique configuration names using distinct()", tags=["database", "query"])
        all_configs = set()
        collection_names = self._db.list_collection_names()
        for collection_name in collection_names:
            if collection_name.startswith("system."):
                continue
            try:
                names = self._db[collection_name].distinct("configurations.name")
                all_configs.update((name for name in names if name))
            except Exception as e:
                trace.warn(
                    "Error fetching configuration names from collection",
                    tags=["database", "query", "error"],
                    collection=collection_name,
                    error=str(e),
                )
                continue
        result = sorted(all_configs)
        trace.debug("Unique configuration names retrieved", tags=["database", "query"], config_count=len(result))
        return result

    def list_collections_optimized(self) -> List[str]:
        trace.debug("Fetching collection names from MongoDB", tags=["database", "query"])
        collection_names = self._db.list_collection_names()
        result = sorted([name for name in collection_names if not name.startswith("system.")])
        trace.debug("Collection names retrieved", tags=["database", "query"], collection_count=len(result))
        return result

    def get_configuration_info_optimized(self) -> List[ConfigurationInfo]:
        trace.debug("Fetching configuration info using aggregation pipeline", tags=["database", "query"])
        merged = {}
        collection_names = self._db.list_collection_names()
        for collection_name in collection_names:
            if collection_name.startswith("system."):
                continue
            try:
                pipeline = [
                    {"$unwind": "$configurations"},
                    {
                        "$group": {
                            "_id": "$configurations.name",
                            "collections": {"$addToSet": "$collection"},
                            "last_assigned": {"$max": "$configurations.assigned"},
                        }
                    },
                    {"$project": {"_id": 0, "name": "$_id", "collections": 1, "last_assigned": 1}},
                ]
                for r in self._db[collection_name].aggregate(pipeline):
                    name = r.get("name")
                    if not name:
                        continue
                    if name not in merged:
                        merged[name] = {
                            "collections": set(r.get("collections", [])),
                            "last_assigned": r.get("last_assigned", ""),
                        }
                    else:
                        merged[name]["collections"].update(r.get("collections", []))
                        new_assigned = r.get("last_assigned", "")
                        if new_assigned > merged[name]["last_assigned"]:
                            merged[name]["last_assigned"] = new_assigned
            except Exception as e:
                trace.warn(
                    "Error aggregating configuration info from collection",
                    tags=["database", "query", "error"],
                    collection=collection_name,
                    error=str(e),
                )
                continue
        result = [
            ConfigurationInfo(
                name=name,
                collection_count=len(data["collections"]),
                collections=sorted(data["collections"]),
                last_assigned=data["last_assigned"],
            )
            for (name, data) in merged.items()
        ]
        result.sort(key=lambda c: c.last_assigned, reverse=True)
        trace.debug("Configuration info retrieved", tags=["database", "query"], config_count=len(result))
        return result

    def get_collection_info_optimized(self) -> List[CollectionInfo]:
        trace.debug("Fetching collection info using aggregation pipeline", tags=["database", "query"])
        results = []
        collection_names = self._db.list_collection_names()
        for collection_name in collection_names:
            if collection_name.startswith("system."):
                continue
            try:
                pipeline = [
                    {
                        "$project": {
                            "collection": 1,
                            "version": 1,
                            "version_int": {
                                "$cond": {
                                    "if": {"$regexMatch": {"input": "$version", "regex": "^[0-9]+$"}},
                                    "then": {"$toInt": "$version"},
                                    "else": 0,
                                }
                            },
                            "created": "$bookkeeping.created",
                        }
                    },
                    {"$sort": {"version_int": -1}},
                    {
                        "$group": {
                            "_id": "$collection",
                            "version_count": {"$sum": 1},
                            "latest_version": {"$first": "$version"},
                            "last_updated": {"$first": "$created"},
                        }
                    },
                    {
                        "$project": {
                            "_id": 0,
                            "name": "$_id",
                            "version_count": 1,
                            "latest_version": 1,
                            "last_updated": 1,
                        }
                    },
                ]
                for r in self._db[collection_name].aggregate(pipeline):
                    results.append(
                        CollectionInfo(
                            name=r.get("name", collection_name),
                            version_count=r.get("version_count", 0),
                            latest_version=r.get("latest_version"),
                            last_updated=r.get("last_updated"),
                        )
                    )
            except Exception as e:
                trace.warn(
                    "Error aggregating collection info, using fallback",
                    tags=["database", "query", "error", "fallback"],
                    collection=collection_name,
                    error=str(e),
                )
                results.append(
                    CollectionInfo(name=collection_name, version_count=0, latest_version=None, last_updated=None)
                )
        results.sort(key=lambda c: c.name)
        trace.debug("Collection info retrieved", tags=["database", "query"], collection_count=len(results))
        return results

    def get_document_by_id_direct(
        self, document_id: str, collection_name: Optional[str] = None
    ) -> Optional[OTSDocument]:
        trace.debug(
            "Fetching document by ID (direct query)",
            tags=["database", "query"],
            document_id=document_id,
            collection=collection_name or "all",
        )
        try:
            object_id = ObjectId(document_id)
            if collection_name:
                doc = self._db[collection_name].find_one({"_id": object_id})
                if doc:
                    doc["_id"] = str(doc["_id"])
                    return OTSDocument(**doc)
            else:
                for coll_name in self._db.list_collection_names():
                    if coll_name.startswith("system."):
                        continue
                    doc = self._db[coll_name].find_one({"_id": object_id})
                    if doc:
                        doc["_id"] = str(doc["_id"])
                        return OTSDocument(**doc)
        except Exception as e:
            trace.error(
                "Failed to fetch document by ID",
                tags=["database", "query", "error"],
                exception=e,
                document_id=document_id,
            )
        return None

    def find_duplicate_versions(self) -> Dict[str, Dict[str, List[str]]]:
        trace.info("Analyzing database for duplicate version numbers", tags=["database", "query"])
        collection_names = [name for name in self._db.list_collection_names() if not name.startswith("system.")]
        pipeline = [
            {"$group": {"_id": "$version", "count": {"$sum": 1}, "doc_ids": {"$push": {"$toString": "$_id"}}}},
            {"$match": {"count": {"$gt": 1}}},
            {"$project": {"_id": 0, "version": "$_id", "doc_ids": 1}},
        ]

        def process_collection(coll_name: str) -> Tuple[str, Dict[str, List[str]]]:
            duplicates = {}
            try:
                for doc in self._db[coll_name].aggregate(pipeline):
                    version = doc.get("version", "0")
                    doc_ids = doc.get("doc_ids", [])
                    if doc_ids:
                        duplicates[version] = doc_ids
            except Exception as e:
                trace.warn(
                    "Error checking collection for duplicate versions",
                    tags=["database", "query", "error"],
                    collection=coll_name,
                    error=str(e),
                )
            return (coll_name, duplicates)

        result: Dict[str, Dict[str, List[str]]] = {}
        max_workers = min(len(collection_names), 8) if collection_names else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_collection, name) for name in collection_names]
            for future in as_completed(futures):
                (coll_name, duplicates) = future.result()
                if duplicates:
                    result[coll_name] = duplicates
        trace.info(
            "Duplicate version analysis complete",
            tags=["database", "query"],
            collections_with_duplicates=len(result),
            collections_queried=len(collection_names),
        )
        return result

    def find_duplicate_collections_in_configs(
        self, progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Dict[str, List[str]]]:
        trace.info("Analyzing configurations for duplicate collection references", tags=["database", "query"])
        collection_names = [name for name in self._db.list_collection_names() if not name.startswith("system.")]
        total_collections = len(collection_names)
        if progress_callback:
            progress_callback(0, total_collections)
        pipeline = [
            {"$unwind": "$configurations"},
            {
                "$group": {
                    "_id": {"config": "$configurations.name", "collection": "$collection"},
                    "count": {"$sum": 1},
                    "doc_ids": {"$push": {"$toString": "$_id"}},
                }
            },
            {"$match": {"count": {"$gt": 1}}},
            {"$project": {"_id": 0, "config_name": "$_id.config", "doc_collection": "$_id.collection", "doc_ids": 1}},
        ]

        def process_collection(coll_name: str) -> List[Dict[str, Any]]:
            try:
                return list(self._db[coll_name].aggregate(pipeline))
            except Exception as e:
                trace.warn(
                    "Error checking collection for duplicate config references",
                    tags=["database", "query", "error"],
                    collection=coll_name,
                    error=str(e),
                )
                return []

        accumulated: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
        max_workers = min(len(collection_names), 8) if collection_names else 1
        completed_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_collection, name): name for name in collection_names}
            for future in as_completed(futures):
                completed_count += 1
                if progress_callback:
                    progress_callback(completed_count, total_collections)
                for doc in future.result():
                    config_name = doc.get("config_name")
                    doc_collection = doc.get("doc_collection")
                    doc_ids = doc.get("doc_ids", [])
                    if config_name and doc_collection and doc_ids:
                        accumulated[config_name][doc_collection].extend(doc_ids)
        result: Dict[str, Dict[str, List[str]]] = {}
        for config_name, collections in accumulated.items():
            filtered_collections = {coll: ids for (coll, ids) in collections.items() if len(ids) > 1}
            if filtered_collections:
                result[config_name] = filtered_collections
        trace.info(
            "Duplicate collection analysis complete",
            tags=["database", "query"],
            configs_with_duplicates=len(result),
            collections_queried=len(collection_names),
        )
        return result

    def _fetch_documents_by_ids_batch(self, document_ids: List[str]) -> Dict[str, OTSDocument]:
        if not document_ids:
            return {}
        object_ids = [ObjectId(doc_id) for doc_id in document_ids]
        object_id_set = set(object_ids)
        collection_names = [name for name in self._db.list_collection_names() if not name.startswith("system.")]
        result: Dict[str, OTSDocument] = {}

        def process_collection(coll_name: str) -> List[OTSDocument]:
            docs = []
            try:
                collection = self._db[coll_name]
                cursor = collection.find({"_id": {"$in": list(object_id_set)}})
                for doc_dict in cursor:
                    try:
                        doc_dict["_id"] = str(doc_dict["_id"])
                        ots_doc = OTSDocument.model_validate(doc_dict)
                        docs.append(ots_doc)
                    except Exception as e:
                        trace.warn(
                            "Failed to parse document in batch fetch",
                            tags=["database", "query", "error"],
                            document_id=str(doc_dict.get("_id")),
                            error=str(e),
                        )
            except Exception as e:
                trace.warn(
                    "Error querying collection for batch fetch",
                    tags=["database", "query", "error"],
                    collection=coll_name,
                    error=str(e),
                )
            return docs

        max_workers = min(len(collection_names), 8) if collection_names else 1
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_collection, name) for name in collection_names]
            for future in as_completed(futures):
                for doc in future.result():
                    result[doc.id] = doc
        trace.debug(
            "Batch document fetch complete",
            tags=["database", "query", "batch"],
            requested=len(document_ids),
            found=len(result),
        )
        return result

    def batch_delete_documents(
        self,
        document_ids: List[str],
        soft_delete: bool = True,
        skip_protected: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BatchOperationResult:
        result = BatchOperationResult()
        total = len(document_ids)
        if not document_ids:
            return result
        trace.info(
            "Bulk delete operation starting",
            tags=["database", "mutation", "bulk"],
            document_count=total,
            soft_delete=soft_delete,
        )
        if progress_callback:
            progress_callback(0, total)
        docs_by_id = self._fetch_documents_by_ids_batch(document_ids)
        operations_by_collection: Dict[str, List[Tuple[str, Any]]] = defaultdict(list)
        timestamp = datetime.now().isoformat()
        for doc_id in document_ids:
            doc = docs_by_id.get(doc_id)
            if doc is None:
                result.failed_count += 1
                result.failed_ids.append(doc_id)
                result.errors[doc_id] = "Document not found"
                continue
            if skip_protected and doc.is_readonly_or_deleted():
                result.skipped_count += 1
                result.skipped_ids.append(doc_id)
                continue
            if soft_delete:
                self._apply_soft_delete(doc)
                doc_dict = doc.model_dump(by_alias=True)
                doc_dict["_id"] = ObjectId(doc_id)
                operations_by_collection[doc.collection].append(
                    (doc_id, UpdateOne({"_id": ObjectId(doc_id)}, {"$set": doc_dict}))
                )
            else:
                operations_by_collection[doc.collection].append((doc_id, DeleteOne({"_id": ObjectId(doc_id)})))
        for coll_name, ops in operations_by_collection.items():
            if not ops:
                continue
            doc_ids_in_batch = [op[0] for op in ops]
            write_ops = [op[1] for op in ops]
            try:
                collection = self._db[coll_name]
                bulk_result = collection.bulk_write(write_ops, ordered=False)
                if soft_delete:
                    success_count = bulk_result.modified_count
                else:
                    success_count = bulk_result.deleted_count
                result.success_count += success_count
                failed_in_batch = len(write_ops) - success_count
                if failed_in_batch > 0:
                    for doc_id in doc_ids_in_batch[success_count:]:
                        result.failed_count += 1
                        result.failed_ids.append(doc_id)
                        result.errors[doc_id] = "Bulk operation may have failed"
                trace.debug(
                    "Bulk write completed for collection",
                    tags=["database", "mutation", "bulk"],
                    collection=coll_name,
                    operations=len(write_ops),
                    success=success_count,
                )
            except BulkWriteError as bwe:
                write_errors = bwe.details.get("writeErrors", [])
                error_indices = {e["index"] for e in write_errors}
                for i, doc_id in enumerate(doc_ids_in_batch):
                    if i in error_indices:
                        result.failed_count += 1
                        result.failed_ids.append(doc_id)
                        error_msg = next(
                            (e["errmsg"] for e in write_errors if e["index"] == i), "Unknown bulk write error"
                        )
                        result.errors[doc_id] = error_msg
                    else:
                        result.success_count += 1
                trace.warn(
                    "Bulk write had partial failures",
                    tags=["database", "mutation", "bulk", "error"],
                    collection=coll_name,
                    total_operations=len(write_ops),
                    errors=len(write_errors),
                )
            except Exception as e:
                for doc_id in doc_ids_in_batch:
                    result.failed_count += 1
                    result.failed_ids.append(doc_id)
                    result.errors[doc_id] = str(e)
                trace.error(
                    "Bulk write failed for collection",
                    tags=["database", "mutation", "bulk", "error"],
                    collection=coll_name,
                    error=str(e),
                )
        if result.success_count > 0 and self._documents is not None:
            deleted_ids = set(document_ids) - set(result.failed_ids) - set(result.skipped_ids)
            if soft_delete:
                for doc_id in deleted_ids:
                    if doc_id in self._documents_by_id:
                        self._documents_by_id[doc_id].bookkeeping.isdeleted = True
            else:
                self._documents = [d for d in self._documents if d.id not in deleted_ids]
                for doc_id in deleted_ids:
                    self._documents_by_id.pop(doc_id, None)
        if progress_callback:
            progress_callback(total, total)
        trace.info(
            "Bulk delete operation complete",
            tags=["database", "mutation", "bulk"],
            success=result.success_count,
            failed=result.failed_count,
            skipped=result.skipped_count,
        )
        return result

    def batch_remove_configurations(
        self,
        items: List[Tuple[str, str]],
        timestamp: str,
        skip_protected: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> BatchOperationResult:
        result = BatchOperationResult()
        total = len(items)
        if not items:
            return result
        trace.info(
            "Bulk remove configuration operation starting", tags=["database", "mutation", "bulk"], item_count=total
        )
        if progress_callback:
            progress_callback(0, total)
        document_ids = list(set((doc_id for (doc_id, _) in items)))
        docs_by_id = self._fetch_documents_by_ids_batch(document_ids)
        operations_by_collection: Dict[str, List[Tuple[str, Any]]] = defaultdict(list)
        for doc_id, config_name in items:
            doc = docs_by_id.get(doc_id)
            if doc is None:
                result.failed_count += 1
                result.failed_ids.append(doc_id)
                result.errors[doc_id] = "Document not found"
                continue
            if skip_protected and doc.is_readonly_or_deleted():
                result.skipped_count += 1
                result.skipped_ids.append(doc_id)
                continue
            (success_removal, _) = self._apply_configuration_removal(doc, config_name, timestamp)
            if not success_removal:
                result.failed_count += 1
                result.failed_ids.append(doc_id)
                result.errors[doc_id] = f"Configuration '{config_name}' not found in document"
                continue
            doc_dict = doc.model_dump(by_alias=True)
            doc_dict["_id"] = ObjectId(doc_id)
            operations_by_collection[doc.collection].append(
                (doc_id, UpdateOne({"_id": ObjectId(doc_id)}, {"$set": doc_dict}))
            )
        for coll_name, ops in operations_by_collection.items():
            if not ops:
                continue
            doc_ids_in_batch = [op[0] for op in ops]
            write_ops = [op[1] for op in ops]
            try:
                collection = self._db[coll_name]
                bulk_result = collection.bulk_write(write_ops, ordered=False)
                success_count = bulk_result.modified_count
                result.success_count += success_count
                failed_in_batch = len(write_ops) - success_count
                if failed_in_batch > 0:
                    for doc_id in doc_ids_in_batch[success_count:]:
                        result.failed_count += 1
                        result.failed_ids.append(doc_id)
                        result.errors[doc_id] = "Bulk update may have failed"
                trace.debug(
                    "Bulk config removal completed for collection",
                    tags=["database", "mutation", "bulk"],
                    collection=coll_name,
                    operations=len(write_ops),
                    success=success_count,
                )
            except BulkWriteError as bwe:
                write_errors = bwe.details.get("writeErrors", [])
                error_indices = {e["index"] for e in write_errors}
                for i, doc_id in enumerate(doc_ids_in_batch):
                    if i in error_indices:
                        result.failed_count += 1
                        result.failed_ids.append(doc_id)
                        error_msg = next(
                            (e["errmsg"] for e in write_errors if e["index"] == i), "Unknown bulk write error"
                        )
                        result.errors[doc_id] = error_msg
                    else:
                        result.success_count += 1
                trace.warn(
                    "Bulk config removal had partial failures",
                    tags=["database", "mutation", "bulk", "error"],
                    collection=coll_name,
                    total_operations=len(write_ops),
                    errors=len(write_errors),
                )
            except Exception as e:
                for doc_id in doc_ids_in_batch:
                    result.failed_count += 1
                    result.failed_ids.append(doc_id)
                    result.errors[doc_id] = str(e)
                trace.error(
                    "Bulk config removal failed for collection",
                    tags=["database", "mutation", "bulk", "error"],
                    collection=coll_name,
                    error=str(e),
                )
        if result.success_count > 0 and self._documents is not None:
            for doc_id, doc in docs_by_id.items():
                if doc_id in self._documents_by_id and doc_id not in result.failed_ids:
                    self._documents_by_id[doc_id] = doc
                    for i, cached_doc in enumerate(self._documents):
                        if cached_doc.id == doc_id:
                            self._documents[i] = doc
                            break
        if progress_callback:
            progress_callback(total, total)
        trace.info(
            "Bulk remove configuration operation complete",
            tags=["database", "mutation", "bulk"],
            success=result.success_count,
            failed=result.failed_count,
            skipped=result.skipped_count,
        )
        return result

    def reload(self) -> None:
        trace.info("Reloading all documents from MongoDB", tags=["database", "lifecycle"])
        self._documents = None
        self._documents_by_id = None
        self._load_all_documents()

    def close(self) -> None:
        if self._client:
            trace.info("Closing MongoDB connection", tags=["database", "lifecycle"])
            self._client.close()
            self._client = None
            self._db = None

    def __del__(self):
        self.close()
