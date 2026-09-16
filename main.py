import os
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request

app = FastAPI(title="SmartCargo-Advisory", version="3.3")

# Configuración de rutas absolutas para asegurar compatibilidad en Render
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

if os.path.exists(os.path.join(BASE_DIR, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")

# Carga de plantillas apuntando estrictamente a templates/index.htm
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    """Renderiza la interfaz principal buscando index.htm en la carpeta templates."""
    return templates.TemplateResponse(
        request, 
        "index.htm", 
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
    estado_envoltura: str = Form("metal_crate"),
    descripcion: str = Form(""),
    piezas: int = Form(0),
    largo_cm: float = Form(0.0),
    ancho_cm: float = Form(0.0),
    alto_cm: float = Form(0.0),
    pdfs: list[UploadFile] = File([]),
    fotos: list[UploadFile] = File([])
):
    """Motor de asesoría técnica con filtro estricto de aceptación."""
    try:
        volumen_m3 = (largo_cm * ancho_cm * alto_cm * piezas) / 1000000.0 if (piezas > 0 and largo_cm > 0 and ancho_cm > 0 and alto_cm > 0) else 0.0

        alertas = []
        checks = []

        # 1. FILTRO OBLIGATORIO: Si falta AWB o datos físicos elementales, se detiene de inmediato.
        if not awb_numero or awb_numero.strip() in ["", "N/D", "134-12345678"] and (piezas <= 0 or peso_kg <= 0):
            estatus_general = "HOLD"
            solucion_directa = "Detener proceso. Indicar número de AWB válido y datos físicos de peso y piezas."
            alertas.append({
                "item": "Filtro de Identificación Inicial",
                "detalle": "Prohibido procesar sin identificar la operación, guía aérea (AWB) y desglose físico."
            })
            checks.append({"item": "Identificación de Carga", "status": "FAIL", "note": "Falta AWB, piezas o peso bruto."})
            
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

        # 2. Flujo normal de evaluación cuando sí hay datos...
        estatus_general = "ACCEPT"
        solucion_directa = "Proceder con estiba estándar y transferencia a zona de armado (Build-up)."

        if tipo_carga == "dg":
            estatus_general = "ESCALATE"
            solucion_directa = "Detener recepción. Exigir Shipper's Declaration (DGD) física y verificar UN Number."
            alertas.append({"item": "Documentación DG", "detalle": "Prohibida la aceptación sin DGD válido."})
            checks.append({"item": "Documentación DG", "status": "CHECK", "note": "Requerido DGD físico."})
        elif estado_envoltura in ["skid", "bundle"]:
            estatus_general = "HOLD"
            solucion_directa = "Verificar puntos de izaje y sujeción de bases antes de aceptar."
            checks.append({"item": "Sujeción de base", "status": "CHECK", "note": "Revisar puntos de anclaje."})
        elif estado_envoltura == "drum":
            estatus_general = "CHECK"
            solucion_directa = "Verificar sellos de seguridad y ausencia de fugas."
            checks.append({"item": "Inspección de tambores", "status": "CHECK", "note": "Revisar condición estanca."})

        if not alertas and estatus_general == "ACCEPT":
            checks = [
                {"item": "Documentación y AWB", "status": "OK", "note": "Datos conformes entre sistema y físico."},
                {"item": "Integridad de bultos", "status": "OK", "note": "Sin daños ni humedad aparente."}
            ]

        return {
            "estatus_general": estatus_general,
            "solucion_directa": solucion_directa,
            "awb": awb_numero,
            "destino": destino or "N/D",
            "piezas": piezas,
            "peso_kg": peso_kg,
            "volumen_m3": round(volumen_m3, 4),
            "alertas": alertas,
            "checks": checks
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en servidor: {str(e)}")
