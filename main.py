import os
import json
from fastapi import FastAPI, Form, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Optional

# Instanciar la aplicación
app = FastAPI(title="SmartCargo Advisory")

# === ENLACE ABSOLUTO SEGURO ENTRE MAIN.PY Y LA CARPETA TEMPLATES ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Configurar Jinja2 apuntando directamente a la ruta absoluta
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Montar archivos estáticos si existe la carpeta static
STATIC_DIR = os.path.join(BASE_DIR, "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Ruta raíz que vincula main.py con templates/index.html
@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/smartcargo/resolver")
async def resolver_carga(
    actor: str = Form("counter"),
    awb_numero: str = Form(""),
    origen: str = Form("MIA"),
    destino: str = Form("BOG"),
    vuelo: str = Form(""),
    aeronave: str = Form("a320"),
    posicion_carga: str = Form("belly"),
    tipo_uld: str = Form("ake"),
    categoria_mercancia: str = Form("general"),
    doc_awb_tipo: str = Form("original"),
    doc_permisos: str = Form("completos"),
    doc_pagos: str = Form("verificado"),
    modo_medicion: str = Form("general"),
    piezas: float = Form(0),
    peso_kg: float = Form(0),
    largo_cm: float = Form(0),
    ancho_cm: float = Form(0),
    alto_cm: float = Form(0),
    detalle_bultos: Optional[str] = Form(None),
    descripcion: str = Form(""),
    pdfs: List[UploadFile] = File([]),
    fotos: List[UploadFile] = File([])
):
    try:
        alertas = []
        checks = []
        
        # 1. Validación de Papelería y Documentación Interna
        if doc_awb_tipo == "copia":
            alertas.append({
                "item": "Control de Documentación (AWB)",
                "detalle": "Se está utilizando una copia o archivo operativo. Verificar que el original (Shipper Copy) esté respaldado en el pouch de la aerolínea."
            })
            checks.append({
                "item": "Air Waybill (AWB)",
                "status": "REVISIÓN",
                "note": "Asegurar copia física fuera del sobre y original dentro del pouch para aduana."
            })
        else:
            checks.append({
                "item": "Air Waybill (AWB)",
                "status": "OK",
                "note": "Documentación original validada correctamente para despacho."
            })

        if doc_permisos == "pendientes":
            alertas.append({
                "item": "Retención Aduanal / OGA",
                "detalle": "Permisos gubernamentales pendientes (FDA/USDA/CITES). La carga no puede liberarse para vuelo hasta autorización."
            })
            checks.append({
                "item": "Permisos Gubernamentales",
                "status": "HOLD",
                "note": "Retener en bodega hasta recepción de certificado oficial impreso o digital."
            })
        else:
            checks.append({
                "item": "Permisos Gubernamentales",
                "status": "OK",
                "note": "Cumplimiento normativo aduanal verificado."
            })

        if doc_pagos == "pendiente":
            alertas.append({
                "item": "Control Financiero",
                "detalle": "Falta confirmación de pago o cheque para liberar la guía aérea."
            })
            checks.append({
                "item": "Finanzas / Vouchers",
                "status": "HOLD",
                "note": "Solicitar comprobante de pago o autorización de crédito antes de aceptar en rampa."
            })
        else:
            checks.append({
                "item": "Finanzas / Vouchers",
                "status": "OK",
                "note": "Verificación financiera y pagos conformes."
            })

        # 2. Cálculo y validación de volumen y peso
        volumen_m3 = 0.0
        if modo_medicion == "detalle" and detalle_bultos:
            try:
                items_lista = json.loads(detalle_bultos)
                checks.append({
                    "item": "Desglose por Artículo",
                    "status": "OK",
                    "note": f"Se registraron {len(items_lista)} grupos de artículos detallados en recepción."
                })
            except:
                pass
        
        if largo_cm > 0 and ancho_cm > 0 and alto_cm > 0 and piezas > 0:
            volumen_m3 = (largo_cm * ancho_cm * alto_cm * piezas) / 1000000.0
        
        # 3. Validación de restricciones de Aeronave y Contorno ULD
        estatus_general = "ACCEPT"
        solucion_directa = "Carga conforme. Proceder a etiquetado, estiba en posición asignada y despacho a rampa."

        if aeronave == "a320" and tipo_uld in ["pmc", "pag"]:
            estatus_general = "HOLD"
            solucion_directa = "Rechazar pallet estándar en A320. Cambiar a contenedor bajo (AKH/LD3-45) o desarmar para carga a granel (Bulk)."
            alertas.append({
                "item": "Incompatibilidad de Aeronave",
                "detalle": "Los narrowbody A320/A321 no admiten pallets de cubierta principal ni contenedores altos."
            })

        if peso_kg > 1588 and tipo_uld == "ake":
            estatus_general = "HOLD"
            solucion_directa = "Exceso de peso para ULD AKE/LD3 (Límite 1,588 kg). Redistribuir la mercancía en dos contenedores o cambiar a pallet."
            alertas.append({
                "item": "Límite de Peso ULD",
                "detalle": "El peso bruto supera el máximo estructural permitido para contenedor AKE."
            })

        if len(alertas) > 0 and estatus_general == "ACCEPT":
            estatus_general = "HOLD"
            solucion_directa = "Resolver las observaciones documentales o financieras antes de la aceptación final en bodega."

        return JSONResponse({
            "estatus_general": estatus_general,
            "solucion_directa": solucion_directa,
            "awb": awb_numero or "N/D",
            "destino": destino.upper(),
            "piezas": piezas,
            "peso_kg": peso_kg,
            "volumen_m3": round(volumen_m3, 4),
            "aeronave": aeronave.upper(),
            "posicion_carga": posicion_carga.upper(),
            "tipo_uld": tipo_uld.upper(),
            "categoria_mercancia": categoria_mercancia.upper(),
            "alertas": alertas,
            "checks": checks
        })

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
