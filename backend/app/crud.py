"""Fábrica de rotas CRUD simples para as entidades do modo Gerenciar."""

import inspect
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .db import get_session


def crud_router(
    *,
    prefix: str,
    model: type,
    schema_in: type[BaseModel],
    schema_out: type[BaseModel],
    filters: tuple[str, ...] = (),
    order_by: tuple[str, ...] = ("id",),
    tag: str,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    def _get_or_404(session: Session, item_id: int):
        obj = session.get(model, item_id)
        if obj is None:
            raise HTTPException(404, f"{tag} {item_id} não encontrado")
        return obj

    def _commit(session: Session):
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise HTTPException(409, f"Conflito de dados: {exc.orig}") from exc

    # Listagem com filtros opcionais por igualdade (ex.: ?subject_id=3).
    # A assinatura é montada em tempo de execução para o FastAPI documentar os filtros.
    def list_items(session: Session, **kwargs: Any):
        stmt = select(model)
        for name in filters:
            value = kwargs.get(name)
            if value is not None:
                stmt = stmt.where(getattr(model, name) == value)
        stmt = stmt.order_by(*(getattr(model, c) for c in order_by))
        return session.scalars(stmt).all()

    params = [inspect.Parameter("session", inspect.Parameter.KEYWORD_ONLY, default=Depends(get_session), annotation=Session)]
    params += [
        inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=Query(None), annotation=int | None)
        for name in filters
    ]
    list_items.__signature__ = inspect.Signature(params)  # type: ignore[attr-defined]
    router.add_api_route("", list_items, methods=["GET"], response_model=list[schema_out])

    @router.post("", response_model=schema_out, status_code=201)
    def create_item(data: schema_in, session: Session = Depends(get_session)):  # type: ignore[valid-type]
        obj = model(**data.model_dump())
        session.add(obj)
        _commit(session)
        session.refresh(obj)
        return obj

    @router.get("/{item_id}", response_model=schema_out)
    def get_item(item_id: int, session: Session = Depends(get_session)):
        return _get_or_404(session, item_id)

    @router.put("/{item_id}", response_model=schema_out)
    def update_item(item_id: int, data: schema_in, session: Session = Depends(get_session)):  # type: ignore[valid-type]
        obj = _get_or_404(session, item_id)
        for key, value in data.model_dump().items():
            setattr(obj, key, value)
        _commit(session)
        session.refresh(obj)
        return obj

    @router.delete("/{item_id}", status_code=204)
    def delete_item(item_id: int, session: Session = Depends(get_session)):
        obj = _get_or_404(session, item_id)
        session.delete(obj)
        _commit(session)

    return router
