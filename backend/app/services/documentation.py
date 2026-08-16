from __future__ import annotations

import copy
import json
import uuid
from urllib.parse import urljoin

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_request import APIRequest
from app.models.collection import Collection
from app.models.folder import Folder
from app.schemas.resources import CollectionCreate, FolderCreate, RequestCreate
from app.services.resources import create_collection, create_folder, create_request


class DocumentationRuleError(Exception):
    pass


_SENSITIVE_NAME_PARTS = {
    "authorization", "proxy-authorization", "cookie", "set-cookie",
    "api-key", "apikey", "auth-token", "access-token", "refresh-token",
    "password", "passwd", "secret", "credential", "credentials", "token",
}


def _is_sensitive_name(name: str) -> bool:
    normalized = name.strip().lower().replace("_", "-")
    return any(part in normalized for part in _SENSITIVE_NAME_PARTS)


def _safe_json_example(value):
    if isinstance(value, dict):
        return {k: ("<redacted>" if _is_sensitive_name(str(k)) else _safe_json_example(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_safe_json_example(item) for item in value]
    return value


def _clean_text(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _parameter_list(operation: dict, path_item: dict) -> tuple[list[dict], list[dict]]:
    headers: list[dict] = []
    query_params: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for source in (path_item.get("parameters", []), operation.get("parameters", [])):
        if not isinstance(source, list):
            continue
        for parameter in source:
            if not isinstance(parameter, dict) or "$ref" in parameter:
                continue
            name = parameter.get("name")
            location = parameter.get("in")
            if not isinstance(name, str) or location not in {"query", "header"}:
                continue
            key = (location, name.lower())
            if key in seen:
                continue
            seen.add(key)
            example = parameter.get("example")
            if example is None:
                schema = parameter.get("schema") or {}
                example = schema.get("example", parameter.get("default", ""))
            item = {"key": name, "value": str(example), "enabled": True}
            (query_params if location == "query" else headers).append(item)
    return headers, query_params


def _request_body(operation: dict) -> tuple[str | None, str | None]:
    body = operation.get("requestBody")
    if not isinstance(body, dict):
        return None, None
    content = body.get("content")
    if not isinstance(content, dict) or not content:
        return None, None
    media_type, definition = next(iter(content.items()))
    if not isinstance(definition, dict):
        return None, media_type
    example = definition.get("example")
    if example is None:
        examples = definition.get("examples")
        if isinstance(examples, dict) and examples:
            first = next(iter(examples.values()))
            if isinstance(first, dict):
                example = first.get("value")
    if example is None:
        schema = definition.get("schema")
        if isinstance(schema, dict) and "example" in schema:
            example = schema["example"]
    if example is None:
        return None, media_type
    if isinstance(example, (dict, list)):
        return json.dumps(example, indent=2), media_type
    return str(example), media_type


def _operation_url(path: str, servers: list | None) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    base = "https://api.example.com"
    if isinstance(servers, list) and servers and isinstance(servers[0], dict):
        candidate = servers[0].get("url")
        if isinstance(candidate, str) and candidate.strip():
            base = candidate.strip()
    return urljoin(base.rstrip("/") + "/", path.lstrip("/"))


def _security_auth(operation: dict, root_security: object) -> str:
    security = operation.get("security", root_security)
    if not security:
        return "none"
    if not isinstance(security, list) or not security or not isinstance(security[0], dict):
        return "none"
    names = list(security[0].keys())
    return "bearer" if any("bearer" in name.lower() for name in names) else (
        "basic" if any("basic" in name.lower() for name in names) else "none"
    )


def _response_example(operation: dict) -> dict:
    responses = operation.get("responses")
    if not isinstance(responses, dict) or not responses:
        return {"description": "Successful response"}
    result: dict = {}
    for code, response in list(responses.items())[:5]:
        if not isinstance(response, dict):
            continue
        entry = {"description": _clean_text(response.get("description"), "Response")}
        content = response.get("content")
        if isinstance(content, dict) and content:
            media, definition = next(iter(content.items()))
            if isinstance(definition, dict):
                example = definition.get("example")
                if example is not None:
                    entry["content"] = {media: {"example": example}}
        result[str(code)] = entry
    return result or {"200": {"description": "Successful response"}}


async def generate_openapi(
    session: AsyncSession, *, workspace_id: uuid.UUID, title: str
) -> dict:
    collections = list(
        await session.scalars(
            select(Collection).where(Collection.workspace_id == workspace_id).order_by(Collection.position, Collection.created_at)
        )
    )
    folders = list(
        await session.scalars(
            select(Folder)
            .join(Collection, Folder.collection_id == Collection.id)
            .where(Collection.workspace_id == workspace_id)
            .order_by(Folder.position, Folder.created_at)
        )
    )
    requests = list(
        await session.scalars(
            select(APIRequest)
            .join(Collection, APIRequest.collection_id == Collection.id)
            .where(Collection.workspace_id == workspace_id)
            .order_by(APIRequest.position, APIRequest.created_at)
        )
    )
    collection_map = {item.id: item for item in collections}
    folder_map = {item.id: item for item in folders}

    paths: dict[str, dict] = {}
    tags: list[dict] = []
    seen_tags: set[str] = set()
    for request in requests:
        collection = collection_map[request.collection_id]
        tag = collection.name
        if tag not in seen_tags:
            seen_tags.add(tag)
            tags.append({"name": tag, "description": collection.description or f"API requests in {tag}"})
        path = request.url
        if path.startswith("http://") or path.startswith("https://"):
            from urllib.parse import urlsplit
            parsed = urlsplit(path)
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
        if not path.startswith("/"):
            path = "/" + path
        headers = []
        for item in request.headers or []:
            if isinstance(item, dict) and item.get("enabled", True):
                key = str(item.get("key", ""))
                if _is_sensitive_name(key):
                    continue
                headers.append({"name": key, "in": "header", "required": False, "schema": {"type": "string"}, "example": str(item.get("value", ""))})
        parameters = headers
        for item in request.query_params or []:
            if isinstance(item, dict) and item.get("enabled", True):
                key = str(item.get("key", ""))
                if _is_sensitive_name(key):
                    continue
                parameters.append({"name": key, "in": "query", "required": False, "schema": {"type": "string"}, "example": str(item.get("value", ""))})
        operation = {
            "operationId": f"request_{request.id.hex}",
            "summary": request.name,
            "description": request.description or "",
            "tags": [tag],
            "parameters": parameters,
            "responses": {"200": {"description": "Successful response"}},
        }
        auth = request.auth_config or {}
        auth_type = auth.get("type") if isinstance(auth, dict) else "none"
        if auth_type == "bearer":
            operation["security"] = [{"bearerAuth": []}]
        elif auth_type == "basic":
            operation["security"] = [{"basicAuth": []}]
        elif auth_type == "none":
            operation["security"] = []
        if request.body is not None:
            media_type = "application/json"
            try:
                parsed_body = json.loads(request.body)
            except (TypeError, json.JSONDecodeError):
                media_type = "text/plain"
                parsed_body = None
            content_definition = {"schema": {"type": "object" if media_type == "application/json" else "string"}}
            if parsed_body is not None:
                content_definition["example"] = _safe_json_example(parsed_body)
            operation["requestBody"] = {"content": {media_type: content_definition}}
        paths.setdefault(path, {})[request.method.lower()] = operation

    return {
        "openapi": "3.0.3",
        "info": {"title": title, "version": "1.0.0", "description": "Generated from APIForge request definitions."},
        "servers": [{"url": "https://api.example.com"}],
        "tags": tags,
        "paths": paths,
        "components": {"securitySchemes": {
            "bearerAuth": {"type": "http", "scheme": "bearer"},
            "basicAuth": {"type": "http", "scheme": "basic"},
        }},
        "x-apiforge": {"workspace_id": str(workspace_id), "generated": True, "collection_count": len(collections), "folder_count": len(folders), "request_count": len(requests)},
    }


async def import_openapi(
    session: AsyncSession, *, workspace_id: uuid.UUID, spec: dict, collection_name: str | None = None
) -> tuple[Collection, int, int]:
    if not isinstance(spec, dict) or not str(spec.get("openapi", "")).startswith(("3.0.", "3.1.")):
        raise DocumentationRuleError("Only OpenAPI 3.0.x and 3.1.x documents are supported.")
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise DocumentationRuleError("OpenAPI document must contain a paths object.")

    title = collection_name or (spec.get("info") or {}).get("title") or "Imported API"
    title = _clean_text(title, "Imported API")[:120]
    info = spec.get("info") or {}
    description = info.get("description") if isinstance(info, dict) else None

    collection = Collection(
        workspace_id=workspace_id,
        name=title,
        description=description if isinstance(description, str) else None,
        position=0,
    )
    session.add(collection)
    await session.flush()

    tags_to_folders: dict[str, Folder] = {}
    folder_count = 0
    request_count = 0
    root_security = spec.get("security")
    servers = spec.get("servers")
    request_positions = 0
    folder_positions = 0

    for raw_path, path_item in paths.items():
        if not isinstance(raw_path, str) or not isinstance(path_item, dict):
            continue
        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue
            tags = operation.get("tags")
            tag = tags[0] if isinstance(tags, list) and tags and isinstance(tags[0], str) else None
            folder_id = None
            if tag:
                if tag not in tags_to_folders:
                    folder = Folder(collection_id=collection.id, parent_id=None, name=tag[:120], position=folder_positions)
                    folder_positions += 1
                    session.add(folder)
                    await session.flush()
                    tags_to_folders[tag] = folder
                    folder_count += 1
                folder_id = tags_to_folders[tag].id

            headers, query_params = _parameter_list(operation, path_item)
            body, media_type = _request_body(operation)
            if body is not None and media_type:
                headers.append({"key": "Content-Type", "value": media_type, "enabled": True})
            url = _operation_url(raw_path, servers)
            name = _clean_text(operation.get("summary") or operation.get("operationId"), f"{method.upper()} {raw_path}")[:160]
            description = operation.get("description") or operation.get("summary")
            auth_type = _security_auth(operation, root_security)
            request = APIRequest(
                collection_id=collection.id,
                folder_id=folder_id,
                name=name,
                description=description if isinstance(description, str) else None,
                method=method.upper(),
                url=url,
                headers=headers,
                query_params=query_params,
                body=body,
                # Credentials are intentionally never imported.
                auth_config={"type": auth_type},
                position=request_positions,
            )
            request_positions += 1
            session.add(request)
            request_count += 1

    await session.commit()
    await session.refresh(collection)
    return collection, folder_count, request_count
