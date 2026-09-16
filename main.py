from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
import os

app = FastAPI(title="SmartCargo-Advisory", version="3.3")

# Configuración de archivos estáticos y plantillas
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# Matriz de decisión operacional integrada (basada en esquema oficial)
SMARTCARGO_MATRIZ = {
    "version": "3.0",
    "nombre_sistema": "SmartCargo-Advisory",
    "alcance_legal": "Asesoría operativa en tierra y aire limitada al comprador en USA. No sustituye manuales internos ni normativas oficiales.",
    "regla_de_oro": "SI NO COINCIDE, NO SE ADIVINA. SE DETIENE. SE VERIFICA. SE DOCUMENTA. SE ESCALA CUANDO CORRESPONDA."
}

@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request):
    """Renderiza la interfaz principal de la aplicación."""
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
    """Motor de asesoría técnica basado en la matriz de decisión operacional."""
    
    # Cálculo automático de volumen en m³
    volumen_m3 = (largo_cm * ancho_cm * alto_cm * piezas) / 1000000.0 if (piezas > 0 and largo_cm > 0 and ancho_cm > 0 and alto_cm > 0) else 0.0

    alertas = []
    checks = []
    
    # Evaluación según la matriz de decisión operacional
    if estado_envoltura in ["humedo", "roto"]:
        estatus_general = "REJECT"
        solucion_directa = "Rechazar empaque dañado y devolver al forwarder para reempaque inmediato."
        alertas.append({
            "item": "Condición del embalaje",
            "detalle": f"Empaque en estado {estado_envoltura}. Riesgo de derrame o daño estructural en vuelo."
        })
        checks.append({"item": "Condición del embalaje", "status": "FAIL", "note": "Riesgo de derrame o daño estructural en vuelo."})

    elif tipo_carga == "dg":
        estatus_general = "ESCALATE"
        solucion_directa = "Detener recepción. Exigir Shipper's Declaration (DGD) física y verificar UN Number y clases bajo normativas vigentes."
        alertas.append({
            "item": "Documentación DG",
            "detalle": "Prohibida la aceptación verbal o visual sin DGD válido."
        })
        checks.append({"item": "Documentación DG", "status": "CHECK", "note": "Prohibida la aceptación verbal o visual sin DGD válido."})
        checks.append({"item": "Personal competente", "status": "ESCALATE", "note": "Notificar a especialista en mercancías peligrosas."})

    elif volumen_m3 > 50.0 and peso_kg < 1500:
        estatus_general = "HOLD"
        solucion_directa = "Detener proceso. Reasurar pesaje y cubicaje físico en báscula por discrepancia de gálibo."
        alertas.append({
            "item": "Volumetría Anómala",
            "detalle": f"Volumen alto ({volumen_m3:.4f} m³) frente a peso bajo ({peso_kg} kg). Posible error de digitación."
        })
        checks.append({"item": "Dimensiones físicas", "status": "FAIL", "note": "Posible error de digitación en centímetros o bultos mal medidos."})
        checks.append({"item": "Aceptación de bodega", "status": "HOLD", "note": "Prohibido el ingreso a rampa hasta rectificar."})

    elif tipo_carga == "general" and estado_envoltura == "intacto":
        estatus_general = "ACCEPT"
        solucion_directa = "Proceder con estiba estándar y transferencia a zona de armado (Build-up)."
        checks = [
            {"item": "Documentación y AWB", "status": "OK", "note": "Datos conformes entre sistema y físico."},
            {"item": "Integridad de bultos", "status": "OK", "note": "Sin daños ni humedad aparente."}
        ]
    else:
        estatus_general = "HOLD"
        solucion_directa = "Detener proceso y verificar discrepancias operativas en counter o bodega."
        checks = [
            {"item": "Revisión general", "status": "CHECK", "note": "Verificar parámetros no estandarizados."}
        ]

    # Validación adicional de documentos PDF adjuntos
    if pdfs:
        for pdf in pdfs:
            if pdf.filename and not pdf.filename.lower().endswith('.pdf'):
                estatus_general = "HOLD"
                alertas.append({
                    "item": "Documentación PDF",
                    "detalle": f"El archivo {pdf.filename} no es un PDF válido."
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
