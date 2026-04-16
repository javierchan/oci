"""Reference-data lookup services for patterns, dictionaries, and assumptions."""

from __future__ import annotations

import re
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.migrations.reference_seed_data import CANVAS_COMBINATIONS
from app.models import AssumptionSet, CatalogIntegration, DictionaryOption, PatternDefinition
from app.schemas.reference import (
    AssumptionSetCreate,
    AssumptionSetListResponse,
    AssumptionSetResponse,
    AssumptionSetUpdate,
    CanvasCombinationResponse,
    CanvasGovernanceResponse,
    DictionaryCategoryListResponse,
    DictionaryCategorySummary,
    DictionaryOptionCreate,
    DictionaryOptionListResponse,
    DictionaryOptionResponse,
    DictionaryOptionUpdate,
    PatternDefinitionCreate,
    PatternDefinitionResponse,
    PatternSupportDimensionsResponse,
    PatternSupportResponse,
    PatternDefinitionUpdate,
    PatternListResponse,
)
from app.services import audit_service
from app.services.pattern_support import get_pattern_support
from app.services.serializers import split_csv

PATTERN_ID_RE = re.compile(r"^#\d{2}$")


def serialize_pattern(pattern: PatternDefinition) -> PatternDefinitionResponse:
    """Convert a pattern model into a response schema."""

    support = get_pattern_support(pattern.pattern_id)
    return PatternDefinitionResponse(
        id=pattern.id,
        pattern_id=pattern.pattern_id,
        name=pattern.name,
        category=pattern.category,
        description=pattern.description,
        components=_extract_component_names(pattern.oci_components),
        component_details=pattern.oci_components,
        when_to_use=pattern.when_to_use,
        when_not_to_use=pattern.when_not_to_use,
        flow=pattern.technical_flow,
        business_value=pattern.business_value,
        is_system=pattern.is_system,
        is_active=pattern.is_active,
        version=pattern.version,
        support=PatternSupportResponse(
            level=support.level,
            badge_label=support.badge_label,
            summary=support.summary,
            parity_ready=support.parity_ready,
            dimensions=PatternSupportDimensionsResponse(
                capture_selection=support.dimensions.capture_selection,
                qa_validation=support.dimensions.qa_validation,
                volumetry=support.dimensions.volumetry,
                dashboard=support.dimensions.dashboard,
                narratives=support.dimensions.narratives,
                exports=support.dimensions.exports,
            ),
        ),
        created_at=pattern.created_at,
        updated_at=pattern.updated_at,
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
        is_volumetric=option.is_volumetric,
        sort_order=option.sort_order,
        is_active=option.is_active,
        version=option.version,
        updated_at=option.updated_at,
    )


def serialize_canvas_combination(combination: dict[str, Any]) -> CanvasCombinationResponse:
    """Convert one governed canvas-combination record into a response schema."""

    return CanvasCombinationResponse(
        code=str(combination["code"]),
        name=str(combination["name"]),
        capture_standard=str(combination["capture_standard"]),
        supported_tool_keys=[
            str(value) for value in cast(list[Any], combination["supported_tool_keys"])
        ],
        compatible_pattern_ids=[
            str(value) for value in cast(list[Any], combination["compatible_pattern_ids"])
        ],
        activates_metrics=[str(value) for value in cast(list[Any], combination["activates_metrics"])],
        activates_volumetric_metrics=bool(combination.get("activates_volumetric_metrics", False)),
        recommended_overlays=[
            str(value) for value in cast(list[Any], combination["recommended_overlays"])
        ],
        guidance=str(combination["guidance"]),
        status=str(combination["status"]),
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


def _validate_pattern_id(pattern_id: str) -> str:
    normalized = pattern_id.strip()
    if not PATTERN_ID_RE.fullmatch(normalized):
        raise HTTPException(
            status_code=400,
            detail={"detail": "Pattern ID must use #NN format.", "error_code": "INVALID_PATTERN_ID"},
        )
    return normalized


def _extract_component_names(component_details: str | None) -> list[str] | None:
    if not component_details:
        return None
    names: list[str] = []
    for line in component_details.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if "—" in cleaned:
            cleaned = cleaned.split("—", 1)[0].strip()
        elif " - " in cleaned:
            cleaned = cleaned.split(" - ", 1)[0].strip()
        names.append(cleaned)
    if not names:
        names = split_csv(component_details)
    return names or None


def _join_component_details(components: list[str] | None, component_details: str | None) -> str | None:
    if component_details is not None:
        normalized_detail = component_details.strip()
        return normalized_detail or None
    if components is None:
        return None
    normalized = [item.strip() for item in components if item.strip()]
    return "\n".join(normalized) if normalized else None


async def _load_pattern(pattern_id: str, db: AsyncSession) -> PatternDefinition:
    pattern = await db.scalar(select(PatternDefinition).where(PatternDefinition.pattern_id == pattern_id))
    if pattern is None:
        raise HTTPException(
            status_code=404,
            detail={"detail": "Pattern not found", "error_code": "PATTERN_NOT_FOUND"},
        )
    return pattern


async def create_pattern(
    data: PatternDefinitionCreate,
    actor_id: str,
    db: AsyncSession,
) -> PatternDefinitionResponse:
    """Create a custom pattern definition and emit an audit event."""

    pattern_id = _validate_pattern_id(data.pattern_id)
    existing = await db.scalar(select(PatternDefinition.id).where(PatternDefinition.pattern_id == pattern_id))
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail={"detail": "Pattern ID already exists", "error_code": "PATTERN_EXISTS"},
        )

    pattern = PatternDefinition(
        pattern_id=pattern_id,
        name=data.name,
        category=data.category,
        description=data.description,
        oci_components=_join_component_details(data.components, data.component_details),
        when_to_use=data.when_to_use,
        when_not_to_use=data.when_not_to_use,
        technical_flow=data.flow,
        business_value=data.business_value,
        is_system=False,
    )
    db.add(pattern)
    await db.flush()
    await db.refresh(pattern)
    response = serialize_pattern(pattern)
    await audit_service.emit(
        event_type="pattern_created",
        entity_type="pattern_definition",
        entity_id=pattern.id,
        actor_id=actor_id,
        old_value=None,
        new_value=response.model_dump(),
        project_id=None,
        db=db,
    )
    return response


async def update_pattern(
    pattern_id: str,
    data: PatternDefinitionUpdate,
    actor_id: str,
    db: AsyncSession,
) -> PatternDefinitionResponse:
    """Patch one pattern definition and emit an audit event."""

    pattern = await _load_pattern(pattern_id, db)
    patch = data.model_dump(exclude_none=True)
    if not patch:
        return serialize_pattern(pattern)

    old_value = serialize_pattern(pattern).model_dump()
    if "components" in patch or "component_details" in patch:
        pattern.oci_components = _join_component_details(data.components, data.component_details)
        patch.pop("components", None)
        patch.pop("component_details", None)
    if "flow" in patch:
        pattern.technical_flow = data.flow
        patch.pop("flow", None)
    if "when_to_use" in patch:
        pattern.when_to_use = data.when_to_use
        patch.pop("when_to_use", None)
    if "when_not_to_use" in patch:
        pattern.when_not_to_use = data.when_not_to_use
        patch.pop("when_not_to_use", None)
    if "business_value" in patch:
        pattern.business_value = data.business_value
        patch.pop("business_value", None)
    for field, value in patch.items():
        setattr(pattern, field, value)
    await db.flush()
    await db.refresh(pattern)
    response = serialize_pattern(pattern)
    await audit_service.emit(
        event_type="pattern_updated",
        entity_type="pattern_definition",
        entity_id=pattern.id,
        actor_id=actor_id,
        old_value=old_value,
        new_value=response.model_dump(),
        project_id=None,
        db=db,
    )
    return response


async def delete_pattern(pattern_id: str, actor_id: str, db: AsyncSession) -> None:
    """Delete one non-system pattern that is not currently referenced by the catalog."""

    pattern = await _load_pattern(pattern_id, db)
    if pattern.is_system:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": "System patterns cannot be deleted.",
                "error_code": "SYSTEM_PATTERN_DELETE_FORBIDDEN",
            },
        )

    in_use_count = await db.scalar(
        select(func.count())
        .select_from(CatalogIntegration)
        .where(CatalogIntegration.selected_pattern == pattern.pattern_id)
    )
    if (in_use_count or 0) > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "detail": f"Pattern in use by {in_use_count} integrations.",
                "error_code": "PATTERN_IN_USE",
            },
        )

    old_value = serialize_pattern(pattern).model_dump()
    pattern_id_internal = pattern.id
    await db.delete(pattern)
    await db.flush()
    await audit_service.emit(
        event_type="pattern_deleted",
        entity_type="pattern_definition",
        entity_id=pattern_id_internal,
        actor_id=actor_id,
        old_value=old_value,
        new_value=None,
        project_id=None,
        db=db,
    )


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


async def get_canvas_governance(db: AsyncSession) -> CanvasGovernanceResponse:
    """Return governed tool, overlay, and combination metadata for the design canvas."""

    tool_options = await db.scalars(
        select(DictionaryOption)
        .where(DictionaryOption.category == "TOOLS", DictionaryOption.is_active.is_(True))
        .order_by(DictionaryOption.sort_order, DictionaryOption.value)
    )
    overlay_options = await db.scalars(
        select(DictionaryOption)
        .where(DictionaryOption.category == "OVERLAYS", DictionaryOption.is_active.is_(True))
        .order_by(DictionaryOption.sort_order, DictionaryOption.value)
    )
    return CanvasGovernanceResponse(
        tools=[serialize_dictionary_option(option) for option in tool_options.all()],
        overlays=[serialize_dictionary_option(option) for option in overlay_options.all()],
        combinations=[serialize_canvas_combination(combination) for combination in CANVAS_COMBINATIONS],
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
