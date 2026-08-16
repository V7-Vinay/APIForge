import base64
import hashlib
import re
import uuid
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.environment import Environment, EnvironmentVariable
from app.schemas.environments import (
    EnvironmentCreate,
    EnvironmentUpdate,
    VariableCreate,
    VariableUpdate,
)


class EnvironmentRuleError(Exception):
    pass


_VAR_RE = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_.-]*)\s*\}\}")


def _fernet() -> Fernet:
    key = settings.ENVIRONMENT_ENCRYPTION_KEY
    if not key:
        if settings.APP_ENV.lower() in {"development", "test", "testing"}:
            digest = hashlib.sha256(b"apiforge-development-environment-key").digest()
            key = base64.urlsafe_b64encode(digest).decode()
        else:
            raise RuntimeError(
                "ENVIRONMENT_ENCRYPTION_KEY must be configured outside development."
            )
    try:
        return Fernet(key.encode())
    except Exception as exc:
        raise RuntimeError(
            "ENVIRONMENT_ENCRYPTION_KEY must be a valid Fernet key."
        ) from exc


def encrypt_value(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise EnvironmentRuleError("Environment variable cannot be decrypted.") from exc


def validate_key(key: str) -> str:
    key = key.strip()
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,99}", key):
        raise EnvironmentRuleError(
            "Variable keys must start with a letter/underscore and contain only letters, numbers, _, . or -."
        )
    return key


async def create_environment(
    session: AsyncSession, *, workspace_id: uuid.UUID, payload: EnvironmentCreate
) -> Environment:
    exists = await session.scalar(
        select(Environment).where(
            Environment.workspace_id == workspace_id, Environment.name == payload.name
        )
    )
    if exists:
        raise EnvironmentRuleError(
            "An environment with this name already exists in the workspace."
        )
    environment = Environment(
        workspace_id=workspace_id, name=payload.name, description=payload.description
    )
    session.add(environment)
    await session.commit()
    await session.refresh(environment)
    return environment


async def list_environments(
    session: AsyncSession, *, workspace_id: uuid.UUID
) -> list[Environment]:
    result = await session.scalars(
        select(Environment)
        .where(Environment.workspace_id == workspace_id)
        .order_by(Environment.name)
    )
    return list(result)


async def get_environment(
    session: AsyncSession, environment_id: uuid.UUID
) -> Environment:
    environment = await session.get(Environment, environment_id)
    if environment is None:
        raise EnvironmentRuleError("Environment not found.")
    return environment


async def update_environment(
    session: AsyncSession, *, environment: Environment, payload: EnvironmentUpdate
) -> Environment:
    if payload.name is not None:
        duplicate = await session.scalar(
            select(Environment).where(
                Environment.workspace_id == environment.workspace_id,
                Environment.name == payload.name,
                Environment.id != environment.id,
            )
        )
        if duplicate:
            raise EnvironmentRuleError(
                "An environment with this name already exists in the workspace."
            )
        environment.name = payload.name
    if payload.description is not None:
        environment.description = payload.description
    await session.commit()
    await session.refresh(environment)
    return environment


async def delete_environment(
    session: AsyncSession, *, environment: Environment
) -> None:
    await session.delete(environment)
    await session.commit()


async def create_variable(
    session: AsyncSession, *, environment: Environment, payload: VariableCreate
) -> EnvironmentVariable:
    key = validate_key(payload.key)
    exists = await session.scalar(
        select(EnvironmentVariable).where(
            EnvironmentVariable.environment_id == environment.id,
            EnvironmentVariable.key == key,
        )
    )
    if exists:
        raise EnvironmentRuleError(
            "A variable with this key already exists in the environment."
        )
    variable = EnvironmentVariable(
        environment_id=environment.id,
        key=key,
        value_ciphertext=encrypt_value(payload.value),
        is_secret=payload.is_secret,
    )
    session.add(variable)
    await session.commit()
    await session.refresh(variable)
    return variable


async def list_variables(
    session: AsyncSession, *, environment_id: uuid.UUID
) -> list[EnvironmentVariable]:
    result = await session.scalars(
        select(EnvironmentVariable)
        .where(EnvironmentVariable.environment_id == environment_id)
        .order_by(EnvironmentVariable.key)
    )
    return list(result)


async def get_variable(
    session: AsyncSession, variable_id: uuid.UUID
) -> EnvironmentVariable:
    variable = await session.get(EnvironmentVariable, variable_id)
    if variable is None:
        raise EnvironmentRuleError("Environment variable not found.")
    return variable


async def update_variable(
    session: AsyncSession, *, variable: EnvironmentVariable, payload: VariableUpdate
) -> EnvironmentVariable:
    if payload.key is not None:
        key = validate_key(payload.key)
        duplicate = await session.scalar(
            select(EnvironmentVariable).where(
                EnvironmentVariable.environment_id == variable.environment_id,
                EnvironmentVariable.key == key,
                EnvironmentVariable.id != variable.id,
            )
        )
        if duplicate:
            raise EnvironmentRuleError(
                "A variable with this key already exists in the environment."
            )
        variable.key = key
    if payload.value is not None:
        variable.value_ciphertext = encrypt_value(payload.value)
    if payload.is_secret is not None:
        variable.is_secret = payload.is_secret
    await session.commit()
    await session.refresh(variable)
    return variable


async def delete_variable(
    session: AsyncSession, *, variable: EnvironmentVariable
) -> None:
    await session.delete(variable)
    await session.commit()


async def resolve_variables(
    session: AsyncSession,
    *,
    environment_id: uuid.UUID,
    text: str,
    reveal_secrets: bool = False
) -> str:
    variables = await list_variables(session, environment_id=environment_id)
    values = {item.key: decrypt_value(item.value_ciphertext) for item in variables}
    missing: set[str] = set()

    def replace(match):
        key = match.group(1)
        if key not in values:
            missing.add(key)
            return match.group(0)
        item = next(v for v in variables if v.key == key)
        if item.is_secret and not reveal_secrets:
            return "********"
        return values[key]

    resolved = _VAR_RE.sub(replace, text)
    if missing:
        raise EnvironmentRuleError(
            "Undefined environment variables: " + ", ".join(sorted(missing))
        )
    return resolved
