from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import List, Optional
from pathlib import Path
import json, re, io, os, hashlib
from pypdf import PdfReader

APP = "SmartCargo Advisory"
VERSION = "10.1.0"
BASE = Path(__file__).parent
DATA = BASE / "data"
TEMPLATE = BASE / "templates" / "index.htm"

app = FastAPI(title=APP, version=VERSION)
if (BASE / "static").exists():
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

RULES = {
    "general": ["AWB/HAWB-MAWB data", "shipper/consignee", "piece count", "gross weight", "dimensions", "security status", "marks/labels", "packaging condition"],
    "dg": ["AWB", "Shipper's Declaration (DGD)", "UN number", "proper shipping name", "class/division", "packing instruction", "quantity", "package type", "acceptance checklist"],
    "perishable": ["AWB", "commodity", "piece count", "gross weight", "packaging", "temperature requirements", "handling codes", "permits/certificates"],
    "avi": ["AWB", "species/animal details", "container specs", "dimensions/weight", "health/veterinary documents", "handling instructions"],
}

@app.get("/", response_class=HTMLResponse)
def home():
    if TEMPLATE.exists():
        # Forzar cabecera UTF-8 estricta
        return HTMLResponse(content=TEMPLATE.read_text(encoding="utf-8"), status_code=200)
    return HTMLResponse(content="<h1>SmartCargo Advisory</h1><p>Falta templates/index.htm</p>", status_code=404)

def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).lower()

def read_pdf(upload: UploadFile):
    raw = upload.file.read()
    if not raw:
        return {"name": upload.filename, "pages": 0, "text": "", "hash": ""}
    try:
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
        return {"name": upload.filename, "pages": len(reader.pages), "text": text[:120000], "hash": hashlib.sha256(raw).hexdigest()}
    except Exception as e:
        return {"name": upload.filename, "pages": 0, "text": "", "hash": hashlib.sha256(raw).hexdigest(), "error": str(e)}

def extract_fields(text):
    t = text or ""
    compact = norm(t)
    out = {}
    patterns = {
        "awb": r"\b(\d{3}[- ]?\d{8})\b",
        "pieces": r"(?:pieces|piezas|pcs)\s*[:\-]?\s*(\d+)",
        "gross_weight": r"(?:gross\s*weight|peso\s*bruto)\s*[:\-]?\s*([\d.,]+)\s*(kg|kgs|lb|lbs)?",
        "destination": r"(?:destination|destino)\s*[:\-]?\s*([A-Z]{3})\b",
        "origin": r"(?:origin|origen)\s*[:\-]?\s*([A-Z]{3})\b",
    }
    for k, p in patterns.items():
        m = re.search(p, t, re.I)
        if m: out[k] = " ".join(x for x in m.groups() if x)
    out["has_dgd"] = bool(re.search(r"shipper.?s declaration|dangerous goods declaration|dgd\b", compact))
    out["has_health_doc"] = bool(re.search(r"health certificate|veterinary|fitosanitary|phytosanitary|sanitary", compact))
    return out

@app.post("/api/smartcargo/resolver")
async def resolver(
    actor: str = Form(...),
    awb_numero: str = Form(...),
    tipo_carga: str = Form(...),
    peso_kg: float = Form(...),
    destino: str = Form(...),
    estado_envoltura: str = Form(...),
    descripcion: str = Form(""),
    vuelo: str = Form(""),
    aeronave: str = Form(""),
    piezas: int = Form(0),
    largo_cm: float = Form(0),
    ancho_cm: float = Form(0),
    alto_cm: float = Form(0),
    fotos: Optional[List[UploadFile]] = File(None),
    pdfs: Optional[List[UploadFile]] = File(None),
):
    # ==========================================
    # BLOQUEO ESTRICTO (HARD STOP CONTRA ERRORES)
    # ==========================================
    
    # 1. Validar formato estricto de AWB (3 dígitos + guión opcional + 8 dígitos = 11 dígitos numéricos)
    awb_clean = re.sub(r"[- ]", "", awb_numero or "")
    if not re.fullmatch(r"\d{11}", awb_clean):
        raise HTTPException(
            status_code=400, 
            detail="RECHAZADO: Formato de AWB inválido. Debe contener exactamente 11 dígitos (Ej: 13412345678 o 134-12345678). Corrija el número para continuar."
        )

    # 2. Validar código IATA de destino (Exactamente 3 letras)
    if not destino or not re.fullmatch(r"[A-Za-z]{3}", destino.strip()):
        raise HTTPException(
            status_code=400, 
            detail="RECHAZADO: Código IATA de destino inválido. Debe ser exactamente de 3 letras (Ej: BOG, MIA)."
        )

    # 3. Validar peso físico obligatorio
    if peso_kg is None or peso_kg <= 0:
        raise HTTPException(
            status_code=400, 
            detail="RECHAZADO: El peso bruto debe ser mayor a 0 kg. Ingrese el peso real verificado en báscula."
        )

    # 4. Validar piezas obligatorias
    if pieces_val := piezas is None or piezas <= 0:
        if piezas <= 0:
            raise HTTPException(
                status_code=400, 
                detail="RECHAZADO: El número de piezas es obligatorio y debe ser mayor a 0."
            )

    # Procesamiento normal de documentos y reglas si pasa el filtro estricto
    pdf_data = [read_pdf(f) for f in (pdfs or [])]
    photo_count = len(fotos or [])
    key = tipo_carga if tipo_carga in RULES else "general"
    
    checks = [{"item": x, "status": "PENDIENTE", "note": "Verificación operativa requerida."} for x in RULES[key]]
    alerts = []
    docs = []
    all_text = "\n".join(p.get("text","") for p in pdf_data)
    extracted = extract_fields(all_text)

    # Evaluación de condiciones físicas y de empaque
    if estado_envoltura in ("humedo", "roto"):
        alerts.append(("Empaque", "Condición no conforme detectada en envoltura.", "HOLD"))

    if descripcion:
        d = norm(descripcion)
        if any(x in d for x in ["mojado", "humedo", "húmedo", "perforado", "roto", "leak", "leaking", "daño"]):
            alerts.append(("Mercancía", "Reporte de daño físico en descripción.", "HOLD"))

    if tipo_carga == "dg":
        docs += ["AWB", "DGD (Declaración de Mercancías Peligrosas)", "Autorizaciones específicas"]
        if not extracted["has_dgd"]:
            alerts.append(("DG", "Falta DGD en documentos adjuntos.", "HOLD"))
    elif tipo_carga == "perishable":
        docs += ["AWB", "Certificado Sanitario / Fitosanitario"]
        if not extracted["has_health_doc"]:
            alerts.append(("Perecedero", "Falta certificado sanitario o fitosanitario en PDFs.", "HOLD"))
    elif tipo_carga == "avi":
        docs += ["AWB", "Documentación Veterinaria y Sanitaria"]
        if not extracted["has_health_doc"]:
            alerts.append(("AVI", "Falta documento veterinario obligatorio.", "HOLD"))
    else:
        docs += ["AWB", "Factura Comercial", "Packing List"]

    if pdf_data and not all_text.strip():
        alerts.append(("PDF", "El documento PDF es una imagen escaneada sin texto legible. Verificación manual obligatoria.", "PENDIENTE"))

    status = "HOLD" if any(a[2] == "HOLD" for a in alerts) else ("PENDIENTE" if alerts else "REVISIÓN COMPLETA")

    # ==========================================
    # RESPUESTAS DIRECTAS, CORTANTES Y DE ESPECIALISTA
    # ==========================================
    if status == "HOLD":
        solution = "RECHAZAR CARGA. No apta para embarque (*Ready for Carriage*). Retener en bodega, corregir no conformidades y reevaluar."
    elif status == "PENDIENTE":
        solution = "RETENER ACEPTACIÓN. Faltan comprobaciones o documentos obligatorios. Verificar antes de proceder."
    else:
        solution = "CARGA CONFORME. Cumple parámetros documentales y físicos básicos. Proceder a aceptación final según normativa aplicable."

    volume_m3 = 0
    if largo_cm > 0 and ancho_cm > 0 and alto_cm > 0 and piezas > 0:
        volume_m3 = (largo_cm * ancho_cm * alto_cm * piezas) / 1_000_000

    return JSONResponse(
        content={
            "version": VERSION,
            "estacion": "MIA",
            "actor": actor,
            "awb": f"{awb_clean[:3]}-{awb_clean[3:]}",
            "tipo_carga": tipo_carga,
            "destino": destino.upper(),
            "vuelo": vuelo.upper(),
            "aeronave": aeronave.upper(),
            "piezas": piezas,
            "peso_kg": peso_kg,
            "dimensiones_cm": [largo_cm, ancho_cm, alto_cm],
            "volumen_m3": round(volume_m3, 4),
            "fotos_recibidas": photo_count,
            "pdfs_recibidos": len(pdf_data),
            "documentos_requeridos_base": docs,
            "documentos_detectados": extracted,
            "checks": checks,
            "alertas": [{"item": a, "detalle": b, "nivel": c} for a, b, c in alerts],
            "estatus_general": status,
            "solucion_directa": solution,
            "nota_operativa": "Control estricto de aceptación. Sujeto a normativas vigentes aplicables."
        },
        media_type="application/json; charset=utf-8"
    )
