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
    """Motor de asesoría técnica basado en la matriz de decisión operacional y ULDs."""
    try:
        # Cálculo automático de volumen en m³
        volumen_m3 = (largo_cm * ancho_cm * alto_cm * piezas) / 1000000.0 if (piezas > 0 and largo_cm > 0 and ancho_cm > 0 and alto_cm > 0) else 0.0

        alertas = []
        checks = []
        estatus_general = "ACCEPT"
        solucion_directa = "Proceder con estiba estándar y transferencia a zona de armado (Build-up)."

        # 1. Evaluación de Mercancías Peligrosas (DG)
        if tipo_carga == "dg":
            estatus_general = "ESCALATE"
            solucion_directa = "Detener recepción. Exigir Shipper's Declaration (DGD) física y verificar UN Number y clases bajo normativas vigentes."
            alertas.append({
                "item": "Documentación DG",
                "detalle": "Prohibida la aceptación verbal o visual sin DGD válido."
            })
            checks.append({"item": "Documentación DG", "status": "CHECK", "note": "Prohibida la aceptación sin DGD válido."})
            checks.append({"item": "Personal competente", "status": "ESCALATE", "note": "Notificar a especialista autorizado."})

        # 2. Evaluación por tipo de envoltura o contenedor ULD
        elif estado_envoltura in ["skid", "bundle"]:
            estatus_general = "HOLD"
            solucion_directa = "Verificar puntos de izaje, centro de gravedad y sujeción de bases antes de aceptar en rampa."
            checks.append({"item": "Sujeción de base", "status": "CHECK", "note": "Revisar puntos de anclaje para carga pesada o irregular."})
        elif estado_envoltura == "drum":
            estatus_general = "CHECK"
            solucion_directa = "Verificar orientación de flechas de posición, sellos de seguridad y ausencia de fugas."
            checks.append({"item": "Inspección de tambores", "status": "CHECK", "note": "Revisar condición estanca y sellos."})
        elif estado_envoltura in ["metal_crate", "pallet", "box"]:
            checks.append({"item": "Tipo de contenedor", "status": "OK", "note": "Contenedor o embalaje compatible con estándares de aceptación."})

        # 3. Control de volumetría anómala
        if volumen_m3 > 50.0 and peso_kg < 1500:
            estatus_general = "HOLD"
            solucion_directa = "Detener proceso. Reasurar pesaje y cubicaje físico en báscula por discrepancia de gálibo."
            alertas.append({
                "item": "Volumetría Anómala",
                "detalle": f"Volumen alto ({volumen_m3:.4f} m³) frente a peso bajo ({peso_kg} kg)."
            })
            checks.append({"item": "Dimensiones físicas", "status": "FAIL", "note": "Posible error de digitación en centímetros o bultos."})

        # 4. Verificación estándar si no hay incidencias
        if not alertas and estatus_general == "ACCEPT":
            checks = [
                {"item": "Documentación y AWB", "status": "OK", "note": "Datos conformes entre sistema y físico."},
                {"item": "Integridad de bultos", "status": "OK", "note": "Sin daños ni humedad aparente."}
            ]

        # Validación de documentos adjuntos
        if pdfs:
            for pdf in pdfs:
                if pdf.filename and not pdf.filename.lower().endswith('.pdf'):
                    estatus_general = "HOLD"
                    alertas.append({
                        "item": "Documentación PDF",
                        "detalle": f"El archivo {pdf.filename} no es un formato PDF válido."
                    })

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
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en servidor: {str(e)}")
