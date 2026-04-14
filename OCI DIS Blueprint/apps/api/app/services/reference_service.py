"""Reference-data lookup services for patterns, dictionaries, and assumptions."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AssumptionSet, DictionaryOption, PatternDefinition
from app.schemas.reference import (
    AssumptionSetCreate,
    AssumptionSetListResponse,
    AssumptionSetResponse,
    AssumptionSetUpdate,
    DictionaryCategoryListResponse,
    DictionaryCategorySummary,
    DictionaryOptionCreate,
    DictionaryOptionListResponse,
    DictionaryOptionResponse,
    DictionaryOptionUpdate,
    PatternDefinitionResponse,
    PatternListResponse,
)
from app.services import audit_service


def serialize_pattern(pattern: PatternDefinition) -> PatternDefinitionResponse:
    """Convert a pattern model into a response schema."""

    return PatternDefinitionResponse(
        id=pattern.id,
        pattern_id=pattern.pattern_id,
        name=pattern.name,
        category=pattern.category,
        description=pattern.description,
        is_active=pattern.is_active,
        version=pattern.version,
    )


def serialize_dictionary_option(option: DictionaryOption) -> DictionaryOptionResponse:
    """Convert a dictionary option model into a response schema."""

    return DictionaryOptionResponse(
        id=option.id,
        category=option.category,
        code=option.code,
        value=option.value,
        description=option.description,
        executions_per_day=option.executions_per_day,
        sort_order=option.sort_order,
        is_active=option.is_active,
    )


def serialize_assumption_set(assumption_set: AssumptionSet) -> AssumptionSetResponse:
    """Convert an assumption set model into a response schema."""

    return AssumptionSetResponse(
        id=assumption_set.id,
        version=assumption_set.version,
        label=assumption_set.label,
        is_default=assumption_set.is_default,
        assumptions=assumption_set.assumptions,
        notes=assumption_set.notes,
        created_at=assumption_set.created_at,
        updated_at=assumption_set.updated_at,
    )


async def list_patterns(db: AsyncSession) -> PatternListResponse:
    """Return all active patterns."""

    result = await db.scalars(
        select(PatternDefinition).where(PatternDefinition.is_active.is_(True)).order_by(PatternDefinition.pattern_id)
    )
    patterns = [serialize_pattern(pattern) for pattern in result.all()]
    return PatternListResponse(patterns=patterns, total=len(patterns))


async def get_pattern(pattern_id: str, db: AsyncSession) -> PatternDefinitionResponse:
    """Return a pattern by business pattern identifier."""

    result = await db.scalar(select(PatternDefinition).where(PatternDefinition.pattern_id == pattern_id))
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Pattern not found", "error_code": "PATTERN_NOT_FOUND"},
        )
    return serialize_pattern(result)


async def list_dictionary_categories(db: AsyncSession) -> DictionaryCategoryListResponse:
    """Return dictionary categories and option counts."""

    result = await db.execute(
        select(DictionaryOption.category, func.count(DictionaryOption.id))
        .group_by(DictionaryOption.category)
        .order_by(DictionaryOption.category)
    )
    categories = [
        DictionaryCategorySummary(category=category, option_count=count)
        for category, count in result.all()
    ]
    return DictionaryCategoryListResponse(categories=categories)


async def list_dictionary_options(category: str, db: AsyncSession) -> DictionaryOptionListResponse:
    """Return options for one dictionary category."""

    normalized_category = category.upper()
    result = await db.scalars(
        select(DictionaryOption)
        .where(DictionaryOption.category == normalized_category)
        .order_by(DictionaryOption.sort_order, DictionaryOption.value)
    )
    return DictionaryOptionListResponse(
        category=normalized_category,
        options=[serialize_dictionary_option(option) for option in result.all()],
    )


async def _load_dictionary_option(category: str, option_id: str, db: AsyncSession) -> DictionaryOption:
    option = await db.scalar(
        select(DictionaryOption).where(
            DictionaryOption.id == option_id,
            DictionaryOption.category == category.upper(),
        )
    )
    if option is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Dictionary option not found", "error_code": "DICTIONARY_OPTION_NOT_FOUND"},
        )
    return option


async def create_dictionary_option(
    category: str,
    body: DictionaryOptionCreate,
    actor_id: str,
    db: AsyncSession,
) -> DictionaryOptionResponse:
    """Create a new governed dictionary option and audit the insert."""

    normalized_category = category.upper()
    option = DictionaryOption(category=normalized_category, **body.model_dump())
    db.add(option)
    await db.flush()
    await db.refresh(option)
    response = serialize_dictionary_option(option)
    await audit_service.emit(
        event_type="dictionary_option_created",
        entity_type="dictionary_option",
        entity_id=option.id,
        actor_id=actor_id,
        old_value=None,
        new_value=response.model_dump(),
        project_id=None,
        db=db,
    )
    return response


async def update_dictionary_option(
    category: str,
    option_id: str,
    body: DictionaryOptionUpdate,
    actor_id: str,
    db: AsyncSession,
) -> DictionaryOptionResponse:
    """Patch a dictionary option and audit the update."""

    option = await _load_dictionary_option(category, option_id, db)
    patch = body.model_dump(exclude_none=True)
    if not patch:
        return serialize_dictionary_option(option)

    old_value = serialize_dictionary_option(option).model_dump()
    for field, value in patch.items():
        setattr(option, field, value)
    await db.flush()
    await db.refresh(option)
    response = serialize_dictionary_option(option)
    await audit_service.emit(
        event_type="dictionary_option_updated",
        entity_type="dictionary_option",
        entity_id=option.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=response.model_dump(),
        project_id=None,
        db=db,
    )
    return response


async def deactivate_dictionary_option(
    category: str,
    option_id: str,
    actor_id: str,
    db: AsyncSession,
) -> DictionaryOptionResponse:
    """Soft-delete one dictionary option by marking it inactive."""

    return await update_dictionary_option(
        category=category,
        option_id=option_id,
        body=DictionaryOptionUpdate(is_active=False),
        actor_id=actor_id,
        db=db,
    )


async def list_assumption_sets(db: AsyncSession) -> AssumptionSetListResponse:
    """List versioned assumption sets."""

    result = await db.scalars(select(AssumptionSet).order_by(AssumptionSet.created_at.desc()))
    return AssumptionSetListResponse(
        assumption_sets=[serialize_assumption_set(item) for item in result.all()]
    )


async def get_assumption_set(version: str, db: AsyncSession) -> AssumptionSetResponse:
    """Load one assumption set by version."""

    result = await db.scalar(select(AssumptionSet).where(AssumptionSet.version == version))
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Assumption set not found", "error_code": "ASSUMPTION_SET_NOT_FOUND"},
        )
    return serialize_assumption_set(result)


async def get_default_assumption_set(db: AsyncSession) -> AssumptionSetResponse:
    """Load the default assumption set."""

    result = await db.scalar(select(AssumptionSet).where(AssumptionSet.is_default.is_(True)))
    if result is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Default assumption set not found", "error_code": "DEFAULT_ASSUMPTION_SET_NOT_FOUND"},
        )
    return serialize_assumption_set(result)


async def _load_assumption_set(version: str, db: AsyncSession) -> AssumptionSet:
    assumption_set = await db.scalar(select(AssumptionSet).where(AssumptionSet.version == version))
    if assumption_set is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Assumption set not found", "error_code": "ASSUMPTION_SET_NOT_FOUND"},
        )
    return assumption_set


async def _set_default_assumption(version: str, db: AsyncSession) -> None:
    all_sets = (await db.scalars(select(AssumptionSet))).all()
    for assumption_set in all_sets:
        assumption_set.is_default = assumption_set.version == version
    await db.flush()


async def create_assumption_set(
    body: AssumptionSetCreate,
    actor_id: str,
    db: AsyncSession,
) -> AssumptionSetResponse:
    """Create a new versioned assumption set and optionally make it default."""

    existing = await db.scalar(select(AssumptionSet.id).where(AssumptionSet.version == body.version))
    if existing is not None:
        raise HTTPException(
            status_code=400,
            detail={"detail": "Assumption set version already exists", "error_code": "ASSUMPTION_SET_EXISTS"},
        )

    assumption_set = AssumptionSet(**body.model_dump())
    db.add(assumption_set)
    await db.flush()
    if body.is_default:
        await _set_default_assumption(body.version, db)
    await db.refresh(assumption_set)
    response = serialize_assumption_set(assumption_set)
    await audit_service.emit(
        event_type="assumption_set_created",
        entity_type="assumption_set",
        entity_id=assumption_set.id,
        actor_id=actor_id,
        old_value=None,
        new_value=response.model_dump(),
        project_id=None,
        db=db,
    )
    return response


async def update_assumption_set(
    version: str,
    body: AssumptionSetUpdate,
    actor_id: str,
    db: AsyncSession,
) -> AssumptionSetResponse:
    """Patch an existing assumption set and audit the change."""

    assumption_set = await _load_assumption_set(version, db)
    patch = body.model_dump(exclude_none=True)
    if not patch:
        return serialize_assumption_set(assumption_set)

    old_value = serialize_assumption_set(assumption_set).model_dump()
    make_default = patch.pop("is_default", None)
    for field, value in patch.items():
        setattr(assumption_set, field, value)
    await db.flush()
    if make_default is True:
        await _set_default_assumption(version, db)
    elif make_default is False:
        assumption_set.is_default = False
        await db.flush()
    await db.refresh(assumption_set)
    response = serialize_assumption_set(assumption_set)
    await audit_service.emit(
        event_type="assumption_set_updated",
        entity_type="assumption_set",
        entity_id=assumption_set.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=response.model_dump(),
        project_id=None,
        db=db,
    )
    return response


async def set_default_assumption_set(
    version: str,
    actor_id: str,
    db: AsyncSession,
) -> AssumptionSetResponse:
    """Promote one assumption set to default and audit the switch."""

    assumption_set = await _load_assumption_set(version, db)
    old_value = serialize_assumption_set(assumption_set).model_dump()
    await _set_default_assumption(version, db)
    await db.refresh(assumption_set)
    response = serialize_assumption_set(assumption_set)
    await audit_service.emit(
        event_type="assumption_set_defaulted",
        entity_type="assumption_set",
        entity_id=assumption_set.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=response.model_dump(),
        project_id=None,
        db=db,
    )
    return response
