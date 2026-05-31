from fastapi import APIRouter, Depends
from pydantic import BaseModel
from ..auth import get_current_user
from ..qr_generator import generar_qr_pago
from ..utils.responses import error

router = APIRouter(tags=["qr"])


class QRRequest(BaseModel):
    monto: float
    descripcion: str


@router.post("/generar-qr")
def generar_qr(qr_data: QRRequest, user: dict = Depends(get_current_user)):
    """Genera un QR de transferencia bancaria."""
    if qr_data.monto <= 0:
        raise error("El monto debe ser mayor a 0", 400)
    return generar_qr_pago(qr_data.monto, qr_data.descripcion)
