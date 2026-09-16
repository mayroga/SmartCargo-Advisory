from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import List, Optional
from pathlib import Path
import json, re, io, os, hashlib
from pypdf import PdfReader

APP = "SmartCargo Advisory"
VERSION = "10.0.0"
BASE = Path(__file__).parent
DATA = BASE / "data"
TEMPLATE = BASE / "templates" / "index.htm"

app = FastAPI(title=APP, version=VERSION)
if (BASE / "static").exists():
    app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")

# Knowledge is deliberately local and editable. Do not represent it as Avianca's
# private system. Carrier/operator/state variations must be checked against current manuals.
RULES = {
    "general": ["AWB/HAWB-MAWB data", "shipper/consignee", "piece count", "gross weight",
                "dimensions", "security status", "marks/labels", "packaging condition",
                "routing/booking", "required export/import documents"],
    "dg": ["AWB", "Shipper's Declaration/DGD when applicable", "UN number",
           "proper shipping name", "class/division", "packing instruction",
           "quantity", "package type", "marks/labels", "operator/state variations",
           "acceptance checklist", "security status"],
    "perishable": ["AWB", "commodity", "piece count", "gross weight", "dimensions",
                   "packaging", "temperature requirements", "handling codes",
                   "flight/routing", "permits/certificates when required",
                   "security status"],
    "avi": ["AWB", "species/animal details", "shipper/consignee", "container",
            "dimensions/weight", "health/veterinary documents when required",
            "routing/flight", "handling instructions", "acceptance checklist"],
}

@app.get("/", response_class=HTMLResponse)
def home():
    if TEMPLATE.exists():
        return TEMPLATE.read_text(encoding="utf-8")
    return "<h1>SmartCargo Advisory</h1><p>Falta templates/index.htm</p>"

def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).lower()

def read_pdf(upload: UploadFile):
    raw = upload.file.read()
    if not raw:
        return {"name": upload.filename, "pages": 0, "text": "", "hash": ""}
    try:
        reader = PdfReader(io.BytesIO(raw))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
        return {"name": upload.filename, "pages": len(reader.pages),
                "text": text[:120000], "hash": hashlib.sha256(raw).hexdigest()}
    except Exception as e:
        return {"name": upload.filename, "pages": 0, "text": "",
                "hash": hashlib.sha256(raw).hexdigest(), "error": str(e)}

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
    for k,p in patterns.items():
        m = re.search(p, t, re.I)
        if m: out[k] = " ".join(x for x in m.groups() if x)
    out["has_dgd"] = bool(re.search(r"shipper.?s declaration|dangerous goods declaration|dgd\b", compact))
    out["has_awb"] = bool(re.search(r"\bair waybill\b|\bawb\b", compact))
    out["has_invoice"] = bool(re.search(r"commercial invoice|invoice|factura comercial", compact))
    out["has_packing_list"] = bool(re.search(r"packing list|lista de empaque", compact))
    out["has_health_doc"] = bool(re.search(r"health certificate|veterinary|fitosanitary|phytosanitary|sanitary", compact))
    return out

def build_checks(actor, category, awb, destination, weight, wrap, pdfs, photos):
    key = category if category in RULES else "general"
    checks = [{"item": x, "status": "PENDIENTE", "note": "Revisar con documento/operación aplicable."}
              for x in RULES[key]]
    alerts = []
    docs = []
    all_text = "\n".join(p.get("text","") for p in pdfs)
    extracted = extract_fields(all_text)

    if not re.fullmatch(r"\d{3}[- ]?\d{8}", awb or ""):
        alerts.append(("AWB", "Formato no validado", "ALERTA"))
    if not destination or len(destination.strip()) != 3:
        alerts.append(("Destino", "Código IATA de 3 letras requerido para validación", "ALERTA"))
    if not weight or weight <= 0:
        alerts.append(("Peso", "Peso bruto requerido", "ALERTA"))
    if wrap in ("humedo","roto"):
        alerts.append(("Empaque", "Condición física reportada como no conforme", "HOLD"))
    if not photos:
        alerts.append(("Fotografías", "No se aportaron fotos; si existen, súbalas para inspección visual", "PENDIENTE"))

    if category == "dg":
        docs += ["AWB", "DGD/Declaración de Mercancías Peligrosas cuando aplique",
                 "Documentos/autorizaciones adicionales según clasificación y ruta"]
        if not extracted["has_dgd"]:
            alerts.append(("DG", "No se identificó una DGD en los PDFs aportados", "HOLD"))
    elif category == "perishable":
        docs += ["AWB", "Documentación sanitaria/fitosanitaria cuando corresponda",
                 "Documentación de temperatura/handling cuando corresponda"]
        if not extracted["has_health_doc"]:
            alerts.append(("Perecedero", "No se identificó certificado sanitario/fitosanitario en los PDFs; verificar si aplica", "PENDIENTE"))
    elif category == "avi":
        docs += ["AWB", "Documentación sanitaria/veterinaria y de importación/exportación cuando corresponda",
                 "Documentos de transporte/handling aplicables"]
        if not extracted["has_health_doc"]:
            alerts.append(("AVI", "No se identificó documento sanitario/veterinario; verificar requisitos de ruta", "PENDIENTE"))
    else:
        docs += ["AWB", "Factura comercial cuando corresponda", "Packing list cuando corresponda",
                 "Documentación de exportación/importación y seguridad aplicable"]

    if pdfs:
        if not all_text.strip():
            alerts.append(("PDF", "El PDF fue recibido pero no contiene texto extraíble; puede ser escaneado/imagen. No se debe declarar verificado.", "PENDIENTE"))
        else:
            if extracted["awb"] and norm(extracted["awb"]) != norm(awb):
                alerts.append(("AWB", f"El AWB extraído del PDF ({extracted['awb']}) no coincide con el ingresado ({awb})", "HOLD"))
    else:
        alerts.append(("Documentos", "No se adjuntaron PDFs para revisión documental", "PENDIENTE"))

    status = "HOLD" if any(a[2]=="HOLD" for a in alerts) else ("PENDIENTE" if alerts else "REVISIÓN COMPLETA")
    return checks, alerts, docs, extracted, status

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
    pdf_data = []
    for f in (pdfs or []):
        pdf_data.append(read_pdf(f))
    photo_count = len(fotos or [])
    checks, alerts, docs, extracted, status = build_checks(
        actor, tipo_carga, awb_numero, destino, peso_kg, estado_envoltura, pdf_data, photo_count
    )

    if descripcion:
        d = norm(descripcion)
        if any(x in d for x in ["mojado","humedo","húmedo","perforado","roto","leak","leaking"]):
            alerts.append(("Mercancía/embalaje", "La descripción reporta posible daño o condición física que requiere revisión", "HOLD"))
            status = "HOLD"

    volume_m3 = 0
    if largo_cm > 0 and ancho_cm > 0 and alto_cm > 0 and piezas > 0:
        volume_m3 = (largo_cm * ancho_cm * alto_cm * piezas) / 1_000_000

    if status == "HOLD":
        solution = "NO CONTINUAR COMO CONFORME. Poner la carga/documentación en revisión y resolver las alertas marcadas antes de aceptar como ready for carriage."
    elif status == "PENDIENTE":
        solution = "No declarar la carga lista todavía. Complete los documentos, datos físicos y verificaciones pendientes."
    else:
        solution = "La información aportada supera las comprobaciones básicas locales. Aún debe contrastarse con booking, seguridad, requisitos del operador, Estado y destino antes de la aceptación final."

    return {
        "version": VERSION,
        "estacion": "MIA",
        "actor": actor,
        "awb": awb_numero,
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
        "alertas": [{"item":a,"detalle":b,"nivel":c} for a,b,c in alerts],
        "estatus_general": status,
        "solucion_directa": solution,
        "nota_operativa": "Herramienta de apoyo. No sustituye manuales vigentes del transportista, IATA/ICAO, seguridad, autoridades, booking/load control ni variaciones de Estado/operador."
    }

# Backward compatibility with the earlier prototype.
@app.post("/api/resolver")
async def legacy_resolver(
    rol: str = Form(...), awb: str = Form(...), tipo: str = Form(...),
    destino: str = Form(...), problema: str = Form(...),
    pdfFile: Optional[UploadFile] = File(None)
):
    return await resolver(
        actor=rol, awb_numero=awb, tipo_carga="dg" if "dg" in norm(tipo) else "general",
        peso_kg=0, destino=destino, estado_envoltura="roto" if "roto" in norm(problema) else "intacto",
        descripcion=problema, vuelo="", aeronave="", piezas=0, largo_cm=0, ancho_cm=0, alto_cm=0,
        fotos=None, pdfs=[pdfFile] if pdfFile else None
    )
