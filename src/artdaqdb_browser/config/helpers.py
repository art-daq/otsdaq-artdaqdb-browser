"""
File: helpers.py
Purpose: Configuration helper functions for building MongoDB commands.
Category: Utility
Author: ArtdaqDB Browser Team
Depends: None
Exports: parse_mongodb_uri, get_mongo_client_cmd, build_mongo_shell_cmd, build_mongodump_cmd, build_mongorestore_cmd, ...
Complexity: Medium | Lines: 416
"""

import shutil
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse
from .schema import AppConfig
from ..trace import trace


def parse_mongodb_uri(uri: str) -> Tuple[str, str, str]:
    parsed = urlparse(uri)
    host = parsed.hostname or "localhost"
    port = str(parsed.port) if parsed.port else "27017"
    database = parsed.path.lstrip("/").split("?")[0] if parsed.path else "admin"
    trace.debug("Parsed MongoDB URI", tags=["config", "database"], host=host, port=port, database=database)
    return (host, port, database)


def get_mongo_client_cmd(config: Optional[AppConfig] = None) -> str:
    if config and config.tools.mongo_shell:
        return config.tools.mongo_shell
    if shutil.which("mongosh"):
        return "mongosh"
    elif shutil.which("mongo"):
        return "mongo"
    return "mongosh"


def build_mongo_shell_cmd(config: AppConfig, database: Optional[str] = None, quiet: bool = True) -> List[str]:
    mongodb_config = config.data_source.mongodb
    uri = mongodb_config.uri
    (host, port, uri_database) = parse_mongodb_uri(uri)
    db = database or uri_database or "admin"
    client = get_mongo_client_cmd(config)
    is_mongosh = "mongosh" in client
    auth_type = mongodb_config.auth.type
    requires_tls = mongodb_config.requires_tls
    trace.debug(
        "Building mongo shell command",
        tags=["config", "database"],
        client=client,
        host=host,
        port=port,
        database=db,
        auth_type=auth_type,
        requires_tls=requires_tls,
    )
    if auth_type == "none":
        connect_uri = f"mongodb://{host}:{port}/{db}"
        timeout_params = []
        if mongodb_config.connect_timeout_ms:
            timeout_params.append(f"connectTimeoutMS={mongodb_config.connect_timeout_ms}")
        if mongodb_config.server_selection_timeout_ms:
            timeout_params.append(f"serverSelectionTimeoutMS={mongodb_config.server_selection_timeout_ms}")
        if timeout_params:
            connect_uri += "?" + "&".join(timeout_params)
        cmd = [client, connect_uri]
        if requires_tls:
            if is_mongosh:
                cmd.append("--tls")
            else:
                cmd.append("--ssl")
        if mongodb_config.direct_connection:
            cmd.append("--directConnection")
    elif auth_type == "x509":
        x509_config = mongodb_config.auth.x509
        cert_dir = x509_config.get_cert_dir_path()
        ca_cert = cert_dir / x509_config.ca_cert
        client_cert = cert_dir / x509_config.client_cert
        connect_uri = f"mongodb://{host}:{port}/{db}"
        uri_params = [
            f"connectTimeoutMS={mongodb_config.connect_timeout_ms}",
            f"authSource={x509_config.auth_source}",
            f"authMechanism={x509_config.auth_mechanism}",
        ]
        connect_uri += "?" + "&".join(uri_params)
        cmd = [client, connect_uri]
        if is_mongosh:
            cmd.extend(["--tls", "--tlsCertificateKeyFile", str(client_cert), "--tlsCAFile", str(ca_cert)])
            if x509_config.allow_invalid_certificates:
                cmd.append("--tlsAllowInvalidCertificates")
            if x509_config.allow_invalid_hostnames:
                cmd.append("--tlsAllowInvalidHostnames")
        else:
            cmd.extend(["--ssl", "--sslPEMKeyFile", str(client_cert), "--sslCAFile", str(ca_cert)])
            if x509_config.allow_invalid_certificates:
                cmd.append("--sslAllowInvalidCertificates")
            if x509_config.allow_invalid_hostnames:
                cmd.append("--sslAllowInvalidHostnames")
    elif auth_type == "userpass":
        userpass_config = mongodb_config.auth.userpass
        connect_uri = f"mongodb://{host}:{port}/{db}"
        uri_params = [
            f"connectTimeoutMS={mongodb_config.connect_timeout_ms}",
            f"authSource={userpass_config.auth_source}",
        ]
        if userpass_config.auth_mechanism != "DEFAULT":
            uri_params.append(f"authMechanism={userpass_config.auth_mechanism}")
        connect_uri += "?" + "&".join(uri_params)
        cmd = [client, connect_uri]
        cmd.extend(["-u", userpass_config.user, "-p", userpass_config.password])
        if requires_tls:
            if is_mongosh:
                cmd.append("--tls")
            else:
                cmd.append("--ssl")
    else:
        raise ValueError(f"Unsupported authentication type: {auth_type}")
    if quiet:
        cmd.append("--quiet")
    return cmd


def build_mongodump_cmd(
    config: AppConfig,
    database: str,
    output_dir: str,
    collections: Optional[List[str]] = None,
    exclude_collections: Optional[List[str]] = None,
) -> List[str]:
    mongodb_config = config.data_source.mongodb
    uri = mongodb_config.uri
    (host, port, _) = parse_mongodb_uri(uri)
    auth_type = mongodb_config.auth.type
    mongodump = config.tools.mongodump
    trace.debug(
        "Building mongodump command",
        tags=["config", "database"],
        host=host,
        port=port,
        database=database,
        auth_type=auth_type,
    )
    cmd = [mongodump, f"--host={host}", f"--port={port}", f"--db={database}", f"--out={output_dir}"]
    if auth_type == "x509":
        x509_config = mongodb_config.auth.x509
        cert_dir = x509_config.get_cert_dir_path()
        ca_cert = cert_dir / x509_config.ca_cert
        client_cert = cert_dir / x509_config.client_cert
        cmd.extend(
            [
                "--ssl",
                f"--sslPEMKeyFile={client_cert}",
                f"--sslCAFile={ca_cert}",
                f"--authenticationMechanism={x509_config.auth_mechanism}",
                f"--authenticationDatabase={x509_config.auth_source}",
            ]
        )
        if x509_config.allow_invalid_certificates:
            cmd.append("--sslAllowInvalidCertificates")
        if x509_config.allow_invalid_hostnames:
            cmd.append("--sslAllowInvalidHostnames")
    elif auth_type == "userpass":
        userpass_config = mongodb_config.auth.userpass
        cmd.extend(
            [
                f"-u={userpass_config.user}",
                f"-p={userpass_config.password}",
                f"--authenticationDatabase={userpass_config.auth_source}",
            ]
        )
        if userpass_config.auth_mechanism != "DEFAULT":
            cmd.append(f"--authenticationMechanism={userpass_config.auth_mechanism}")
    if auth_type == "none" and mongodb_config.requires_tls:
        cmd.append("--ssl")
    if collections:
        for coll in collections:
            cmd.extend(["--collection", coll])
    if exclude_collections:
        for coll in exclude_collections:
            cmd.extend(["--excludeCollection", coll])
    return cmd


def build_mongorestore_cmd(
    config: AppConfig,
    database: str,
    input_dir: str,
    host_override: Optional[str] = None,
    port_override: Optional[str] = None,
    drop_existing: bool = False,
    exclude_collections: Optional[List[str]] = None,
) -> List[str]:
    mongodb_config = config.data_source.mongodb
    uri = mongodb_config.uri
    (host, port, _) = parse_mongodb_uri(uri)
    if host_override:
        host = host_override
    if port_override:
        port = port_override
    auth_type = mongodb_config.auth.type
    mongorestore = config.tools.mongorestore
    trace.debug(
        "Building mongorestore command",
        tags=["config", "database"],
        host=host,
        port=port,
        database=database,
        auth_type=auth_type,
    )
    cmd = [mongorestore, f"--host={host}", f"--port={port}", f"--db={database}"]
    if auth_type == "x509":
        x509_config = mongodb_config.auth.x509
        cert_dir = x509_config.get_cert_dir_path()
        ca_cert = cert_dir / x509_config.ca_cert
        client_cert = cert_dir / x509_config.client_cert
        cmd.extend(
            [
                "--ssl",
                f"--sslPEMKeyFile={client_cert}",
                f"--sslCAFile={ca_cert}",
                f"--authenticationMechanism={x509_config.auth_mechanism}",
                f"--authenticationDatabase={x509_config.auth_source}",
            ]
        )
        if x509_config.allow_invalid_certificates:
            cmd.append("--sslAllowInvalidCertificates")
        if x509_config.allow_invalid_hostnames:
            cmd.append("--sslAllowInvalidHostnames")
    elif auth_type == "userpass":
        userpass_config = mongodb_config.auth.userpass
        cmd.extend(
            [
                f"-u={userpass_config.user}",
                f"-p={userpass_config.password}",
                f"--authenticationDatabase={userpass_config.auth_source}",
            ]
        )
        if userpass_config.auth_mechanism != "DEFAULT":
            cmd.append(f"--authenticationMechanism={userpass_config.auth_mechanism}")
    if auth_type == "none" and mongodb_config.requires_tls:
        cmd.append("--ssl")
    if drop_existing:
        cmd.append("--drop")
    if exclude_collections:
        for collection in exclude_collections:
            cmd.append(f"--excludeCollection={collection}")
    cmd.append(input_dir)
    return cmd


def get_server_display_info(config: AppConfig) -> str:
    uri = config.data_source.mongodb.uri
    (host, port, _) = parse_mongodb_uri(uri)
    auth_type = config.data_source.mongodb.auth.type
    auth_display = {"none": "no auth", "x509": "X.509", "userpass": "user/pass"}.get(auth_type, auth_type)
    return f"{host}:{port} ({auth_display})"
