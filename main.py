import os
import re
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ============================================================
# SMARTCARGO — MOTOR PRINCIPAL
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
RULES_FILE = BASE_DIR / "smartcargo_rules.json"

app = FastAPI(title="SMARTCARGO", version="5.0.0")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============================================================
# REGLAS
# ============================================================

def cargar_reglas() -> Dict[str, Any]:
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[SMARTCARGO] Error cargando reglas: {e}")
        return {}


RULES = cargar_reglas()


# ============================================================
# UTILIDADES
# ============================================================

def texto(valor: Any) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def normalizar(valor: Any) -> str:
    s = texto(valor).lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def numero(valor: Any) -> float:
    if valor is None:
        return 0.0
    s = str(valor).replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group()) if m else 0.0


def entero(valor: Any) -> int:
    try:
        return int(round(numero(valor)))
    except Exception:
        return 0


def agregar(problemas: List[Dict[str, Any]], codigo: str,
            estado: str, mensaje: str, accion: str = ""):
    problemas.append({
        "codigo": codigo,
        "estado": estado,
        "mensaje": mensaje,
        "accion": accion
    })


def tiene_error(problemas: List[Dict[str, Any]]) -> bool:
    return any(p["estado"] in ("ERROR", "BLOQUEADO") for p in problemas)


def tiene_revision(problemas: List[Dict[str, Any]]) -> bool:
    return any(p["estado"] == "REVISAR" for p in problemas)


def resultado_final(problemas: List[Dict[str, Any]]) -> str:
    if tiene_error(problemas):
        return "CORREGIR"
    if tiene_revision(problemas):
        return "REVISAR"
    return "LISTO"


# ============================================================
# PDF
# ============================================================

def extraer_pdf(archivo: UploadFile) -> Dict[str, Any]:
    """
    Lee un PDF real cuando existe un lector PDF disponible.
    No inventa texto si el PDF no puede leerse.
    """

    nombre = texto(archivo.filename)

    if not nombre.lower().endswith(".pdf"):
        return {
            "ok": False,
            "estado": "ERROR",
            "codigo": "DOC001",
            "mensaje": "El archivo no es un PDF valido.",
            "texto": "",
            "paginas": 0
        }

    try:
        contenido = archivo.file.read()
    except Exception:
        contenido = b""

    if not contenido:
        return {
            "ok": False,
            "estado": "ERROR",
            "codigo": "DOC002",
            "mensaje": "El archivo no contiene informacion util.",
            "texto": "",
            "paginas": 0
        }

    # Intentar PyPDF2
    lector = None

    try:
        from pypdf import PdfReader
        import io

        lector = PdfReader(io.BytesIO(contenido))

    except Exception:
        try:
            from PyPDF2 import PdfReader
            import io

            lector = PdfReader(io.BytesIO(contenido))

        except Exception:
            return {
                "ok": False,
                "estado": "REVISAR",
                "codigo": "DOC007",
                "mensaje": "No se pudo leer el PDF con el lector disponible.",
                "texto": "",
                "paginas": 0
            }

    textos = []
    errores = []

    try:
        paginas = len(lector.pages)
    except Exception:
        paginas = 0

    if paginas == 0:
        return {
            "ok": False,
            "estado": "ERROR",
            "codigo": "DOC002",
            "mensaje": "El PDF no contiene paginas utilizables.",
            "texto": "",
            "paginas": 0
        }

    for i, pagina in enumerate(lector.pages, start=1):
        try:
            t = pagina.extract_text() or ""
            t = t.strip()

            if not t:
                errores.append({
                    "pagina": i,
                    "codigo": "DOC003",
                    "estado": "ERROR",
                    "mensaje": f"La pagina {i} no contiene texto util.",
                    "accion": "Revisa la pagina o sube una copia legible."
                })
                textos.append("")
                continue

            # Elimina espacios excesivos
            limpio = re.sub(r"\s+", " ", t).strip()

            # Detectar basura evidente de OCR/extraccion
            caracteres = re.sub(r"\s", "", limpio)

            if len(caracteres) < 3:
                errores.append({
                    "pagina": i,
                    "codigo": "DOC005",
                    "estado": "ERROR",
                    "mensaje": f"La pagina {i} no contiene informacion suficiente.",
                    "accion": "Sube una copia correcta."
                })
                textos.append("")
                continue

            # Proporcion de caracteres alfanumericos
            alnum = sum(c.isalnum() for c in caracteres)
            proporcion = alnum / max(len(caracteres), 1)

            if proporcion < 0.25:
                errores.append({
                    "pagina": i,
                    "codigo": "DOC005",
                    "estado": "ERROR",
                    "mensaje": f"La pagina {i} contiene caracteres que no pueden verificarse.",
                    "accion": "Revisa el documento y sube una copia legible."
                })
                textos.append("")
                continue

            textos.append(limpio)

        except Exception:
            errores.append({
                "pagina": i,
                "codigo": "DOC004",
                "estado": "ERROR",
                "mensaje": f"No se pudo leer correctamente la pagina {i}.",
                "accion": "Sube una copia mas clara."
            })
            textos.append("")

    texto_total = "\n".join(t for t in textos if t)

    return {
        "ok": not errores,
        "estado": "ERROR" if errores else "OK",
        "codigo": "",
        "mensaje": "",
        "texto": texto_total,
        "paginas": paginas,
        "errores": errores
    }


# ============================================================
# TEXTO DEL PDF
# ============================================================

def texto_pdf_contiene(texto_pdf: str, termino: str) -> bool:
    return normalizar(termino) in normalizar(texto_pdf)


def parece_documento_relacionado(texto_pdf: str, tipo_carga: str) -> bool:
    """
    Filtro conservador.
    Si el PDF contiene vocabulario claramente relacionado,
    se acepta para revisión.
    Si no hay ninguna señal, se marca para revisión y no se inventa.
    """

    t = normalizar(texto_pdf)

    palabras_generales = [
        "awb",
        "air waybill",
        "shipper",
        "consignee",
        "cargo",
        "freight",
        "carga",
        "peso",
        "weight",
        "pieces",
        "pieces",
        "piezas",
        "description",
        "descripcion",
        "invoice",
        "factura",
        "packing",
        "embalaje",
        "permit",
        "permiso",
        "certificate",
        "certificado",
        "shipment",
        "embarque",
        "transport"
    ]

    especiales = {
        "peligrosa": [
            "dangerous goods",
            "dangerous",
            "hazmat",
            "iata",
            "un ",
            "class",
            "packing instruction",
            "mercancia peligrosa"
        ],
        "perecedera": [
            "perishable",
            "perecedera",
            "temperature",
            "temperatura",
            "fresh",
            "frozen"
        ],
        "animal_vivo": [
            "live animal",
            "animal vivo",
            "animal",
            "veterinary",
            "veterinario"
        ],
        "farmaceutica": [
            "pharmaceutical",
            "pharma",
            "medicamento",
            "medicine",
            "temperature"
        ]
    }

    if any(p in t for p in palabras_generales):
        return True

    for p in especiales.get(normalizar(tipo_carga), []):
        if p in t:
            return True

    return False


# ============================================================
# EXTRAER CAMPOS SENCILLOS DEL TEXTO
# ============================================================

def extraer_numero_patron(texto_pdf: str, patrones: List[str]) -> float:
    for patron in patrones:
        m = re.search(patron, texto_pdf, re.I)
        if m:
            try:
                return float(m.group(1).replace(",", "."))
            except Exception:
                pass
    return 0.0


def extraer_datos_pdf(texto_pdf: str) -> Dict[str, Any]:
    return {
        "piezas": extraer_numero_patron(
            texto_pdf,
            [
                r"(?:pieces|piezas|pcs)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)"
            ]
        ),
        "peso": extraer_numero_patron(
            texto_pdf,
            [
                r"(?:weight|peso|gross weight|gross)\s*[:\-]?\s*(\d+(?:[.,]\d+)?)"
            ]
        )
    }


# ============================================================
# VALIDACION DE DATOS
# ============================================================

def validar_datos_carga(
    problemas: List[Dict[str, Any]],
    piezas: Any,
    peso: Any,
    largo: Any,
    ancho: Any,
    alto: Any
):
    p = entero(piezas)
    w = numero(peso)
    l = numero(largo)
    a = numero(ancho)
    h = numero(alto)

    if p <= 0:
        agregar(
            problemas,
            "CAR001",
            "ERROR",
            "La cantidad de piezas debe ser mayor que cero.",
            "Corrige la cantidad de piezas."
        )

    if w <= 0:
        agregar(
            problemas,
            "CAR002",
            "ERROR",
            "El peso debe ser mayor que cero.",
            "Corrige el peso de la carga."
        )

    dimensiones = [l, a, h]

    if any(x < 0 for x in dimensiones):
        agregar(
            problemas,
            "CAR003",
            "ERROR",
            "Las dimensiones no pueden ser negativas.",
            "Corrige las dimensiones."
        )

    if any(x == 0 for x in dimensiones):
        agregar(
            problemas,
            "CAR004",
            "REVISAR",
            "Faltan una o mas dimensiones.",
            "Completa las dimensiones antes de continuar."
        )


def calcular_volumen(largo: Any, ancho: Any, alto: Any, piezas: Any = 1) -> float:
    l = numero(largo)
    a = numero(ancho)
    h = numero(alto)
    p = max(entero(piezas), 1)

    if l <= 0 or a <= 0 or h <= 0:
        return 0.0

    return round(l * a * h * p, 4)


# ============================================================
# CONSISTENCIA PDF VS DATOS DECLARADOS
# ============================================================

def comparar_pdf(
    problemas: List[Dict[str, Any]],
    datos_pdf: Dict[str, Any],
    piezas: Any,
    peso: Any
):
    piezas_pdf = numero(datos_pdf.get("piezas"))
    peso_pdf = numero(datos_pdf.get("peso"))

    piezas_form = entero(piezas)
    peso_form = numero(peso)

    if piezas_pdf > 0 and piezas_form > 0 and piezas_pdf != piezas_form:
        agregar(
            problemas,
            "CON001",
            "ERROR",
            "La cantidad de piezas no coincide entre el documento y los datos declarados.",
            "Corrige la cantidad antes de continuar."
        )

    if peso_pdf > 0 and peso_form > 0:
        diferencia = abs(peso_pdf - peso_form)

        # No se considera diferencia por pequeños decimales.
        tolerancia = max(0.01, peso_form * 0.001)

        if diferencia > tolerancia:
            agregar(
                problemas,
                "CON002",
                "ERROR",
                "El peso no coincide entre el documento y los datos declarados.",
                "Verifica el peso y corrige la informacion."
            )


# ============================================================
# REGLAS DE CARGA
# ============================================================

def revisar_tipo_carga(
    problemas: List[Dict[str, Any]],
    tipo_carga: str,
    descripcion: str
):
    tipo = normalizar(tipo_carga)
    desc = normalizar(descripcion)

    if not tipo:
        agregar(
            problemas,
            "CAR005",
            "ERROR",
            "No se ha indicado el tipo de carga.",
            "Selecciona el tipo de carga."
        )
        return

    especiales = {
        "peligrosa": ["dangerous", "hazmat", "mercancia peligrosa"],
        "perecedera": ["perishable", "perecedera", "frozen", "fresh"],
        "animal_vivo": ["animal", "live animal", "animal vivo"],
        "farmaceutica": ["pharma", "pharmaceutical", "medicine", "medicamento"],
        "valiosa": ["valuable", "valiosa"]
    }

    if tipo in especiales and not desc:
        agregar(
            problemas,
            "ESP001",
            "REVISAR",
            "Esta carga necesita una descripcion antes de continuar.",
            "Escribe una descripcion clara de la mercancia."
        )


def revisar_embalaje(
    problemas: List[Dict[str, Any]],
    embalaje: str
):
    e = normalizar(embalaje)

    if not e:
        agregar(
            problemas,
            "EMB001",
            "REVISAR",
            "No se ha indicado la condicion del embalaje.",
            "Indica como se encuentra el embalaje."
        )
        return

    if e in ("danado", "dañado", "roto", "humedo", "húmedo", "deformado"):
        agregar(
            problemas,
            "EMB002",
            "REVISAR",
            "El embalaje presenta una condicion que debe revisarse antes de continuar.",
            "Corrige o revisa la condicion del embalaje."
        )


# ============================================================
# FOTOS
# ============================================================

def revisar_fotos(
    problemas: List[Dict[str, Any]],
    archivos: List[UploadFile]
):
    archivos_validos = [
        f for f in archivos
        if f and texto(f.filename)
    ]

    if len(archivos_validos) > 3:
        agregar(
            problemas,
            "FOTO001",
            "REVISAR",
            "Se han agregado mas de 3 fotografias.",
            "Usa las fotografias mas utiles para la revision."
        )

    for archivo in archivos_validos:
        ext = Path(archivo.filename).suffix.lower()

        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            agregar(
                problemas,
                "FOTO002",
                "ERROR",
                f"La fotografia '{archivo.filename}' no tiene un formato permitido.",
                "Sube una fotografia JPG, PNG o WEBP."
            )


# ============================================================
# ENDPOINT PRINCIPAL
# ============================================================

@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": "SMARTCARGO",
        "version": "5.0.0",
        "rules_loaded": bool(RULES)
    }


@app.post("/api/smartcargo/resolver")
async def resolver(
    request: Request,
    rol: str = Form(""),
    tipo_carga: str = Form("general"),
    descripcion: str = Form(""),
    piezas: str = Form("0"),
    peso: str = Form("0"),
    largo: str = Form("0"),
    ancho: str = Form("0"),
    alto: str = Form("0"),
    embalaje: str = Form(""),
    shipper: str = Form(""),
    consignee: str = Form(""),
    origen: str = Form(""),
    destino: str = Form(""),
    awb: str = Form(""),
    documentos: List[UploadFile] = File(default=[]),
    fotos: List[UploadFile] = File(default=[])
):
    problemas: List[Dict[str, Any]] = []

    rol = normalizar(rol)
    tipo_carga = normalizar(tipo_carga)

    # --------------------------------------------------------
    # ROL
    # --------------------------------------------------------

    roles_validos = {
        "camionero",
        "dueno",
        "dueño",
        "forwarder",
        "counter"
    }

    if rol not in roles_validos:
        agregar(
            problemas,
            "ROL001",
            "ERROR",
            "Selecciona un rol para comenzar.",
            "Selecciona camionero, dueño, forwarder o agente de counter."
        )

    # --------------------------------------------------------
    # DATOS BASICOS
    # --------------------------------------------------------

    validar_datos_carga(
        problemas,
        piezas,
        peso,
        largo,
        ancho,
        alto
    )

    revisar_tipo_carga(
        problemas,
        tipo_carga,
        descripcion
    )

    revisar_embalaje(
        problemas,
        embalaje
    )

    # --------------------------------------------------------
    # DATOS IDENTIFICATIVOS
    # --------------------------------------------------------

    if not descripcion.strip():
        agregar(
            problemas,
            "DAT001",
            "ERROR",
            "Falta la descripcion de la mercancia.",
            "Escribe una descripcion clara."
        )

    # Para forwarder y counter la consistencia documental
    # es mas importante.
    if rol in ("forwarder", "counter"):
        if not shipper.strip():
            agregar(
                problemas,
                "DAT002",
                "REVISAR",
                "Falta el remitente.",
                "Completa el remitente."
            )

        if not consignee.strip():
            agregar(
                problemas,
                "DAT003",
                "REVISAR",
                "Falta el destinatario.",
                "Completa el destinatario."
            )

        if not origen.strip():
            agregar(
                problemas,
                "DAT004",
                "REVISAR",
                "Falta el origen.",
                "Completa el origen."
            )

        if not destino.strip():
            agregar(
                problemas,
                "DAT005",
                "REVISAR",
                "Falta el destino.",
                "Completa el destino."
            )

    # --------------------------------------------------------
    # AWB
    # --------------------------------------------------------

    if awb.strip():
        awb_limpio = re.sub(r"[\s\-]", "", awb)

        # Si se proporciona un AWB de 11 digitos,
        # comprobamos el prefijo 134.
        if len(awb_limpio) >= 3 and awb_limpio[:3].isdigit():
            if awb_limpio[:3] != "134":
                agregar(
                    problemas,
                    "AWB001",
                    "REVISAR",
                    "El numero de AWB indicado no comienza con el prefijo esperado para esta aplicacion.",
                    "Verifica el numero de AWB antes de continuar."
                )

    # --------------------------------------------------------
    # FOTOS
    # --------------------------------------------------------

    revisar_fotos(problemas, fotos)

    # --------------------------------------------------------
    # DOCUMENTOS PDF
    # --------------------------------------------------------

    documentos_resultado = []

    for archivo in documentos:
        if not archivo or not archivo.filename:
            continue

        resultado_pdf = extraer_pdf(archivo)

        documentos_resultado.append({
            "nombre": archivo.filename,
            "paginas": resultado_pdf.get("paginas", 0),
            "texto": resultado_pdf.get("texto", ""),
            "estado": resultado_pdf.get("estado", ""),
            "errores": resultado_pdf.get("errores", [])
        })

        # Errores encontrados en paginas
        for error in resultado_pdf.get("errores", []):
            agregar(
                problemas,
                error["codigo"],
                error["estado"],
                error["mensaje"],
                error["accion"]
            )

        texto_documento = resultado_pdf.get("texto", "")

        if texto_documento:
            # Si no parece relacionado, no lo aceptamos
            # silenciosamente.
            if not parece_documento_relacionado(
                texto_documento,
                tipo_carga
            ):
                agregar(
                    problemas,
                    "DOC006",
                    "ERROR",
                    f"El documento '{archivo.filename}' no parece corresponder con la operacion de carga.",
                    "Sube el documento correcto."
                )

            datos_pdf = extraer_datos_pdf(texto_documento)

            comparar_pdf(
                problemas,
                datos_pdf,
                piezas,
                peso
            )

    # Para forwarder/counter, la ausencia total de documentos
    # merece revision.
    if rol in ("forwarder", "counter") and not documentos:
        agregar(
            problemas,
            "DOC008",
            "REVISAR",
            "No se ha cargado ningun documento para revisar.",
            "Carga los documentos disponibles antes de continuar."
        )

    # --------------------------------------------------------
    # CALCULO DE VOLUMEN
    # --------------------------------------------------------

    volumen = calcular_volumen(
        largo,
        ancho,
        alto,
        piezas
    )

    peso_num = numero(peso)

    densidad = 0.0

    if volumen > 0 and peso_num > 0:
        densidad = round(peso_num / volumen, 4)

    # No rechazamos por densidad solamente.
    # Si es inusual, se marca para comprobacion.
    if volumen > 0 and peso_num > 0 and densidad < 0.01:
        agregar(
            problemas,
            "CAR006",
            "REVISAR",
            "La relacion entre peso y volumen parece inusual.",
            "Verifica nuevamente peso y dimensiones."
        )

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    estado = resultado_final(problemas)

    resumen = {
        "LISTO": "La revision previa no encontro problemas pendientes.",
        "CORREGIR": "Hay informacion o documentos que deben corregirse antes de continuar.",
        "REVISAR": "Hay informacion que no puede confirmarse y debe revisarse antes de continuar."
    }[estado]

    return JSONResponse({
        "ok": estado == "LISTO",
        "estado": estado,
        "puede_continuar": estado == "LISTO",
        "rol": rol,
        "tipo_carga": tipo_carga,
        "descripcion": descripcion,
        "piezas": entero(piezas),
        "peso": peso_num,
        "dimensiones": {
            "largo": numero(largo),
            "ancho": numero(ancho),
            "alto": numero(alto)
        },
        "volumen": volumen,
        "densidad": densidad,
        "awb": awb,
        "documentos": documentos_resultado,
        "cantidad_documentos": len(documentos_resultado),
        "cantidad_fotos": len([f for f in fotos if f and f.filename]),
        "problemas": problemas,
        "total_problemas": len(problemas),
        "resumen": resumen,
        "regla_de_oro": (
            "NO ADIVINAR. Si algo no puede verificarse, "
            "debe revisarse o corregirse antes de continuar."
        )
    })


# ============================================================
# EJECUCION LOCAL
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000))
    )
