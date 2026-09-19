import os
import json
import re
from typing import List, Optional

from fastapi import FastAPI, Form, File, UploadFile, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ============================================================
# SMARTCARGO ADVISORY
# ============================================================

app = FastAPI(title="SmartCargo Advisory")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
RULES_FILE = os.path.join(BASE_DIR, "smartcargo_rules.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")

templates = Jinja2Templates(directory=TEMPLATES_DIR)
templates.env.cache = None

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ============================================================
# CARGAR REGLAS
# ============================================================

def cargar_reglas():
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("smartcargo_advisory_engine", {})
    except Exception as e:
        raise RuntimeError(f"No se pudo cargar smartcargo_rules.json: {e}")


RULES = cargar_reglas()


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def regla_por_condicion(**kwargs):
    for regla in RULES.get("matriz_decision_operacional", []):
        if all(regla.get(k) == v for k, v in kwargs.items()):
            return regla
    return None


def agregar_regla(alertas, checks, regla):
    if not regla:
        return

    for p in regla.get("puntos_criticos", []):
        checks.append({
            "item": p.get("item", "Control"),
            "status": p.get("status", "CHECK"),
            "note": p.get("note", "")
        })

    mandato = regla.get("mandato", "HOLD")

    if mandato != "ACCEPT":
        alertas.append({
            "item": "Regla Operacional",
            "detalle": regla.get("instruccion_directa", "")
        })


def calcular_volumen_general(piezas, largo, ancho, alto):
    if piezas > 0 and largo > 0 and ancho > 0 and alto > 0:
        return (largo * ancho * alto * piezas) / 1000000.0
    return 0.0


def calcular_volumen_detalle(detalle_bultos):
    """
    El frontend envía cada artículo como:
    Descripción: 2pz (100x50x40cm, 20kg)
    """
    total = 0.0

    if not detalle_bultos:
        return total

    try:
        items = json.loads(detalle_bultos)
    except Exception:
        return total

    patron = re.compile(
        r":\s*(\d+(?:\.\d+)?)pz\s*"
        r"\((\d+(?:\.\d+)?)x"
        r"(\d+(?:\.\d+)?)x"
        r"(\d+(?:\.\d+)?)cm",
        re.I
    )

    for item in items:
        if not isinstance(item, str):
            continue

        m = patron.search(item)
        if not m:
            continue

        piezas = float(m.group(1))
        largo = float(m.group(2))
        ancho = float(m.group(3))
        alto = float(m.group(4))

        total += (largo * ancho * alto * piezas) / 1000000.0

    return total


def contiene_dano(texto):
    texto = (texto or "").lower()

    palabras = [
        "humedo", "húmedo",
        "humedad",
        "mojado",
        "mojada",
        "wet",
        "moisture",
        "wetness",
        "roto",
        "rota",
        "rotura",
        "dañado",
        "danado",
        "damage",
        "damaged",
        "broken",
        "abierto",
        "abierta",
        "open",
        "leak",
        "derrame"
    ]

    return any(p in texto for p in palabras)


# ============================================================
# RUTA PRINCIPAL
# ============================================================

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


# ============================================================
# MOTOR PRINCIPAL
# ============================================================

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

        estatus_general = "ACCEPT"
        solucion_directa = (
            "Carga conforme. Proceder a etiquetado, estiba en "
            "posición asignada y despacho a rampa."
        )

        # ====================================================
        # 1. DOCUMENTACIÓN
        # ====================================================

        if doc_awb_tipo == "copia":
            alertas.append({
                "item": "Control de Documentación (AWB)",
                "detalle": (
                    "Se está utilizando una copia o archivo operativo. "
                    "Verificar respaldo documental y requisitos aplicables."
                )
            })
            checks.append({
                "item": "Air Waybill (AWB)",
                "status": "REVISIÓN",
                "note": (
                    "Verificar correspondencia entre AWB, sistema, "
                    "documentos físicos y pouch."
                )
            })
        else:
            checks.append({
                "item": "Air Waybill (AWB)",
                "status": "OK",
                "note": "Tipo de documentación registrado para revisión."
            })

        if doc_permisos == "pendientes":
            estatus_general = "HOLD"
            solucion_directa = (
                "Detener la liberación. Verificar y completar los "
                "permisos o autorizaciones requeridos antes de continuar."
            )
            alertas.append({
                "item": "Permisos Gubernamentales / OGA",
                "detalle": (
                    "Existen permisos pendientes. La operación requiere "
                    "verificación documental antes de continuar."
                )
            })
            checks.append({
                "item": "Permisos Gubernamentales",
                "status": "HOLD",
                "note": "Retener hasta verificar la documentación requerida."
            })
        else:
            checks.append({
                "item": "Permisos Gubernamentales",
                "status": "OK",
                "note": "No se registraron permisos pendientes."
            })

        if doc_pagos == "pendiente":
            estatus_general = "HOLD"
            solucion_directa = (
                "Detener la liberación hasta verificar el pago, voucher "
                "o autorización financiera correspondiente."
            )
            alertas.append({
                "item": "Control Financiero",
                "detalle": "Falta confirmación financiera para continuar."
            })
            checks.append({
                "item": "Finanzas / Vouchers",
                "status": "HOLD",
                "note": "Verificar comprobante o autorización antes de liberar."
            })
        else:
            checks.append({
                "item": "Finanzas / Vouchers",
                "status": "OK",
                "note": "No se registró pago pendiente."
            })

        # ====================================================
        # 2. MEDIDAS Y VOLUMEN
        # ====================================================

        if modo_medicion == "detalle":
            volumen_m3 = calcular_volumen_detalle(detalle_bultos)

            try:
                items_lista = json.loads(detalle_bultos or "[]")
            except Exception:
                items_lista = []

            checks.append({
                "item": "Desglose por Artículo",
                "status": "OK" if items_lista else "CHECK",
                "note": (
                    f"Se registraron {len(items_lista)} grupos de artículos."
                    if items_lista
                    else "No se recibió un desglose válido."
                )
            })
        else:
            volumen_m3 = calcular_volumen_general(
                piezas,
                largo_cm,
                ancho_cm,
                alto_cm
            )

        # ====================================================
        # 3. DENSIDAD / VOLUMEN ANÓMALO
        # Regla del smartcargo_rules.json
        # ====================================================

        if volumen_m3 > 50 and peso_kg < 1500:
            regla = regla_por_condicion(
                condicion_volumetrica="anomala_baja_densidad"
            )

            if regla:
                estatus_general = regla.get("mandato", "HOLD")
                solucion_directa = regla.get(
                    "instruccion_directa",
                    "Detener proceso y verificar peso y cubicaje."
                )
                agregar_regla(alertas, checks, regla)

        # ====================================================
        # 4. CARGA GENERAL + DAÑO FÍSICO
        # ====================================================

        if categoria_mercancia == "general":

            if contiene_dano(descripcion):
                regla = regla_por_condicion(
                    tipo_carga="general",
                    envoltura="humedo_o_roto"
                )

                if regla:
                    estatus_general = regla.get("mandato", "REJECT")
                    solucion_directa = regla.get(
                        "instruccion_directa",
                        "Detener y verificar la condición del embalaje."
                    )
                    agregar_regla(alertas, checks, regla)

            else:
                regla = regla_por_condicion(
                    tipo_carga="general",
                    envoltura="intacto"
                )

                if regla:
                    agregar_regla(alertas, checks, regla)

        # ====================================================
        # 5. MERCANCÍAS PELIGROSAS
        # ====================================================

        if categoria_mercancia == "dg":
            regla = regla_por_condicion(tipo_carga="dg")

            if regla:
                estatus_general = regla.get("mandato", "ESCALATE")
                solucion_directa = regla.get(
                    "instruccion_directa",
                    "Detener recepción y escalar a personal competente."
                )
                agregar_regla(alertas, checks, regla)

        # ====================================================
        # 6. AERONAVE / ULD
        # ====================================================

        if aeronave == "a320" and tipo_uld in ["pmc", "pag"]:
            estatus_general = "HOLD"
            solucion_directa = (
                "Detener la operación y verificar la compatibilidad de "
                "la unidad con la aeronave seleccionada."
            )

            alertas.append({
                "item": "Compatibilidad Aeronave / ULD",
                "detalle": (
                    "La combinación seleccionada requiere verificación "
                    "de compatibilidad antes de continuar."
                )
            })

            checks.append({
                "item": "Compatibilidad Aeronave / ULD",
                "status": "HOLD",
                "note": "Verificar contorno, posición y limitaciones aplicables."
            })

        # ====================================================
        # 7. PESO AKE
        # ====================================================

        if peso_kg > 1588 and tipo_uld == "ake":
            estatus_general = "HOLD"
            solucion_directa = (
                "Detener la operación y verificar el peso permitido "
                "para la configuración y posición seleccionadas."
            )

            alertas.append({
                "item": "Peso ULD",
                "detalle": (
                    "El peso registrado supera el parámetro configurado "
                    "para esta revisión del ULD AKE."
                )
            })

            checks.append({
                "item": "Peso ULD",
                "status": "HOLD",
                "note": "Verificar peso, configuración, posición y límites vigentes."
            })

        # ====================================================
        # 8. VALIDACIÓN FINAL
        # ====================================================

        if estatus_general == "ACCEPT" and alertas:
            estatus_general = "HOLD"
            solucion_directa = (
                "Resolver las observaciones identificadas antes de "
                "la aceptación final."
            )

        # ====================================================
        # 9. RESPUESTA
        # ====================================================

        return JSONResponse({
            "estatus_general": estatus_general,
            "solucion_directa": solucion_directa,
            "awb": awb_numero or "N/D",
            "origen": origen.upper(),
            "destino": destino.upper(),
            "vuelo": vuelo.upper(),
            "actor": actor,
            "piezas": piezas,
            "peso_kg": peso_kg,
            "volumen_m3": round(volumen_m3, 4),
            "aeronave": aeronave.upper(),
            "posicion_carga": posicion_carga.upper(),
            "tipo_uld": tipo_uld.upper(),
            "categoria_mercancia": categoria_mercancia.upper(),
            "modo_medicion": modo_medicion,
            "pdfs_recibidos": len(pdfs),
            "fotos_recibidas": len(fotos),
            "alertas": alertas,
            "checks": checks,
            "regla_de_oro": RULES.get("regla_de_oro", "")
        })

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Error en SmartCargo Advisory: {str(e)}"
        )


# ============================================================
# EJECUCIÓN LOCAL
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000))
    )
