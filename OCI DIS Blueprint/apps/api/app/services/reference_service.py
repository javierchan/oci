"""Reference-data lookup services for patterns, dictionaries, and assumptions."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AssumptionSet, DictionaryOption, PatternDefinition
from app.schemas.reference import (
    AssumptionSetListResponse,
    AssumptionSetResponse,
    DictionaryCategoryListResponse,
    DictionaryCategorySummary,
    DictionaryOptionListResponse,
    DictionaryOptionResponse,
    PatternDefinitionResponse,
    PatternListResponse,
)


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
