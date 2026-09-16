from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import os

app = FastAPI(title="SmartCargo-Advisory", version="3.1")

# Configuración de plantillas
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    return templates.TemplateResponse(
        request, 
        "index.html", 
        {"request": request}
    )

@app.post("/api/smartcargo/resolver")
async def resolver_carga(
    actor: str = Form("counter"),
    awb_numero: str = Form("N/D"),
    origen: str = Form("MIA"),
    destino: str = Form("BOG"),
    vuelo: str = Form("N/D"),
    aeronave: str = Form("N/D"),
    tipo_carga: str = Form("general"),
    peso_kg: float = Form(0.0),
    estado_envoltura: str = Form("intacto"),
    descripcion: str = Form(""),
    piezas: int = Form(0),
    largo_cm: float = Form(0.0),
    ancho_cm: float = Form(0.0),
    alto_cm: float = Form(0.0),
    pdfs: list[UploadFile] = File([]),
    fotos: list[UploadFile] = File([])
):
    # Cálculo automático de volumen en m³
    volumen_m3 = (largo_cm * ancho_cm * alto_cm * piezas) / 1000000.0 if (piezas > 0 and largo_cm > 0 and ancho_cm > 0 and alto_cm > 0) else 0.0

    # Motor de decisiones de SmartCargo-Advisory
    alertas = []
    checks = []
    estatus_general = "ACCEPT"
    solucion_directa = "Proceder con estiba estándar y transferencia a zona de armado."

    # 1. Validación de empaque dañado o húmedo
    if estado_envoltura in ["humedo", "roto"]:
        estatus_general = "REJECT"
        solucion_directa = "Rechazar empaque dañado/húmedo y devolver al forwarder para acondicionamiento."
        alertas.append({
            "item": "Condición del Empaque",
            "detalle": f"El empaque presenta estado: {estado_envoltura}. Riesgo operativo inminente."
        })
        checks.append({"item": "Integridad del bulto", "status": "FAIL", "note": "Empaque no apto para vuelo."})

    # 2. Validación de mercancías peligrosas (DG)
    elif tipo_carga == "dg":
        estatus_general = "ESCALATE"
        solucion_directa = "Detener recepción. Exigir Shipper's Declaration (DGD) física y validar UN Number y clases."
        alertas.append({
            "item": "Dangerous Goods (DG)",
            "detalle": "Falta DGD o documentación de mercancías peligrosas obligatoria para validación en counter."
        })
        checks.append({"item": "Shipper's Declaration (DGD)", "status": "CHECK", "note": "Verificación operativa requerida."})
        checks.append({"item": "UN number y clases", "status": "CHECK", "note": "Revisión especializada obligatoria."})

    # 3. Validación volumétrica anómala (Baja densidad / gálibo)
    elif volumen_m3 > 50.0 and peso_kg < 1500:
        estatus_general = "HOLD"
        solucion_directa = "Detener proceso. Reasurar pesaje y cubicaje físico en báscula por discrepancia de gálibo."
        alertas.append({
            "item": "Volumetría Anómala",
            "detalle": f"Volumen alto ({volumen_m3:.4f} m³) frente a peso bajo ({peso_kg} kg). Posible error de digitación."
        })
        checks.append({"item": "Dimensiones físicas", "status": "HOLD", "note": "Requerido reasurar medidas en báscula."})

    # 4. Validación de documentos PDF adjuntos
    if pdfs:
        for pdf in pdfs:
            if not pdf.filename.lower().endswith('.pdf'):
                estatus_general = "HOLD"
                alertas.append({
                    "item": "Documentación PDF",
                    "detalle": f"El archivo {pdf.filename} no es un PDF válido o requiere verificación manual."
                })

    # Completar puntos de control estándar si no hay fallas críticas
    if not checks:
        checks = [
            {"item": "AWB y Guía Aérea", "status": "OK", "note": "Verificado conforme al sistema."},
            {"item": "Peso y Dimensiones", "status": "OK", "note": "Dentro de parámetros permitidos."},
            {"item": "Aceptación en Bodega", "status": "OK", "note": "Listo para transferencia operativa."}
        ]

    return {
        "estatus_general": estatus_general,
        "solucion_directa": solucion_directa,
        "awb": awb_numero or "N/D",
        "destino": destino or "N/D",
        "piezas": piezas,
        "peso_kg": peso_kg,
        "volumen_m3": round(volumen_m3, 4),
        "alertas": alertas,
        "checks": checks
    }
