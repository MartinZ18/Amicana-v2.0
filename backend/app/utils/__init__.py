"""Utilidades compartidas. Reexporta las funciones de uso histórico para
mantener compatibilidad con `from ..utils import serialize_row`."""

from datetime import date, datetime


def serialize_row(row: dict) -> dict:
    """Convierte campos datetime/date de un dict de BD a strings JSON-serializables."""
    for k, v in row.items():
        if isinstance(v, datetime):
            row[k] = v.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(v, date):
            row[k] = v.strftime("%Y-%m-%d")
        elif not isinstance(v, (str, int, float, bool, list, dict)) and v is not None:
            row[k] = str(v)
    return row


__all__ = ["serialize_row"]
