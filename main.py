import os
import re
import json
import shutil
import tempfile
import base64
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
RULES_FILE = BASE_DIR / "smartcargo_rules.json"
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="SMARTCARGO",
    version="7.0.0",
    description="Pre-revisión documental, física y visual de carga."
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.cache = None


def cargar_reglas() -> dict:
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


RULES = cargar_reglas()

ROLES = {
    "camionero": "Camionero",
    "dueno": "Dueño de la mercancía",
    "forwarder": "Forwarder",
    "counter": "Agente de Counter"
}

TIPOS_CARGA = {
    "general",
    "perecedera",
    "animal_vivo",
    "peligrosa",
    "valiosa",
    "farmaceutica",
    "otra"
}

EMBALAJES = {
    "intacto",
    "dañado",
    "húmedo",
    "roto",
    "deformado",
    "no_verificable"
}

EXTENSIONES_IMAGEN = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif"
}


def limpiar(valor: Any) -> str:
    if valor is None:
        return ""
    return str(valor).strip()


def numero(valor: Any) -> float:
    try:
        return float(str(valor).replace(",", ".").strip())
    except Exception:
        return 0.0


def entero(valor: Any) -> int:
    try:
        return int(float(str(valor).strip()))
    except Exception:
        return 0


def normalizar(texto: str) -> str:
    texto = limpiar(texto).lower()
    return re.sub(r"\s+", " ", texto)


def agregar(problemas, estado, mensaje, accion="", codigo=""):
    problemas.append({
        "estado": estado,
        "mensaje": mensaje,
        "accion": accion,
        "codigo": codigo
    })


def extraer_pdf(path: Path) -> dict:
    resultado = {
        "ok": False,
        "texto": "",
        "paginas": 0,
        "vacio": False,
        "ilegible": False,
        "error": ""
    }

    if PdfReader is None:
        resultado["error"] = "Lector PDF no disponible."
        return resultado

    try:
        reader = PdfReader(str(path))
        resultado["paginas"] = len(reader.pages)

        partes = []

        for pagina in reader.pages:
            try:
                partes.append(pagina.extract_text() or "")
            except Exception:
                partes.append("")

        texto = "\n".join(partes).strip()
        limpio = re.sub(r"\s+", " ", texto)

        resultado["texto"] = limpio
        resultado["vacio"] = not bool(limpio)

        if limpio:
            alfanum = len(
                re.findall(
                    r"[A-Za-zÁÉÍÓÚáéíóúÑñ0-9]",
                    limpio
                )
            )

            total = len(limpio)

            if alfanum < 8 or (
                total > 30 and
                alfanum / total < 0.15
            ):
                resultado["ilegible"] = True

        resultado["ok"] = (
            bool(limpio)
            and not resultado["ilegible"]
        )

        return resultado

    except Exception as e:
        resultado["error"] = str(e)
        return resultado


def guardar_temporal(upload: UploadFile) -> Path:
    sufijo = Path(
        upload.filename or ""
    ).suffix.lower() or ".bin"

    fd, nombre = tempfile.mkstemp(
        suffix=sufijo,
        dir=str(UPLOAD_DIR)
    )

    os.close(fd)

    path = Path(nombre)

    with open(path, "wb") as f:
        shutil.copyfileobj(upload.file, f)

    return path


def extraer_campos_pdf(texto: str) -> dict:
    t = normalizar(texto)

    datos = {
        "awb": "",
        "piezas": "",
        "peso": "",
        "origen": "",
        "destino": ""
    }

    m = re.search(r"\b(134[- ]?\d{8})\b", t)

    if m:
        datos["awb"] = re.sub(
            r"[ -]",
            "",
            m.group(1)
        )

    patrones_piezas = [
        r"(?:pieces|piece|piezas|bultos|packages)\s*[:\-]?\s*(\d+)",
        r"\bpcs\s*[:\-]?\s*(\d+)"
    ]

    for patron in patrones_piezas:
        m = re.search(patron, t)

        if m:
            datos["piezas"] = m.group(1)
            break

    patrones_peso = [
        r"(?:gross weight|gross wt|peso bruto|peso total|weight)"
        r"\s*[:\-]?\s*([\d.,]+)\s*(?:kg|kgs)?",
        r"\b([\d.,]+)\s*kg\b"
    ]

    for patron in patrones_peso:
        m = re.search(patron, t)

        if m:
            datos["peso"] = m.group(1).replace(",", "")
            break

    m = re.search(
        r"(?:origin|origen)\s*[:\-]?\s*([a-z0-9 .,'/-]{2,60})",
        t
    )

    if m:
        datos["origen"] = m.group(1).strip()

    m = re.search(
        r"(?:destination|destino)\s*[:\-]?\s*([a-z0-9 .,'/-]{2,60})",
        t
    )

    if m:
        datos["destino"] = m.group(1).strip()

    return datos


def revisar_basicos(data: dict, problemas: list):
    rol = limpiar(data.get("rol"))
    tipo = limpiar(data.get("tipo_carga"))
    descripcion = limpiar(data.get("descripcion"))
    piezas = entero(data.get("piezas"))
    peso = numero(data.get("peso"))
    embalaje = limpiar(data.get("embalaje"))

    if rol not in ROLES:
        agregar(
            problemas,
            "CORREGIR",
            "No se identificó correctamente el perfil del usuario.",
            "Selecciona nuevamente el perfil.",
            "ROL"
        )

    if tipo not in TIPOS_CARGA:
        agregar(
            problemas,
            "CORREGIR",
            "No se indicó correctamente el tipo de carga.",
            "Selecciona el tipo de mercancía.",
            "TIPO_CARGA"
        )

    if not descripcion or len(descripcion) < 3:
        agregar(
            problemas,
            "CORREGIR",
            "Falta una descripción suficiente de la mercancía.",
            "Describe qué contiene la carga.",
            "DESCRIPCION"
        )

    if piezas <= 0:
        agregar(
            problemas,
            "CORREGIR",
            "La cantidad de piezas no es válida.",
            "Introduce el número real de piezas.",
            "PIEZAS"
        )

    if peso <= 0:
        agregar(
            problemas,
            "CORREGIR",
            "El peso total no es válido.",
            "Introduce el peso real en kilogramos.",
            "PESO"
        )

    if embalaje not in EMBALAJES:
        agregar(
            problemas,
            "CORREGIR",
            "No se indicó el estado del embalaje.",
            "Selecciona el estado real del embalaje.",
            "EMBALAJE"
        )


def revisar_dimensiones(data: dict, problemas: list):
    largo = numero(data.get("largo"))
    ancho = numero(data.get("ancho"))
    alto = numero(data.get("alto"))

    valores = [largo, ancho, alto]
    presentes = [x > 0 for x in valores]

    if any(presentes) and not all(presentes):
        agregar(
            problemas,
            "CORREGIR",
            "Las dimensiones están incompletas.",
            "Introduce largo, ancho y alto, o deja las tres vacías.",
            "DIMENSIONES"
        )

    if any(x < 0 for x in valores):
        agregar(
            problemas,
            "CORREGIR",
            "Una dimensión no puede ser negativa.",
            "Corrige las dimensiones.",
            "DIMENSION_NEGATIVA"
        )


def revisar_embalaje(data: dict, problemas: list):
    estado = limpiar(data.get("embalaje"))

    if estado in {
        "dañado",
        "húmedo",
        "roto",
        "deformado"
    }:
        agregar(
            problemas,
            "CORREGIR",
            "El embalaje presenta una condición que debe corregirse o verificarse antes de presentar la carga.",
            "Corrige, reemplaza o haz revisar el embalaje antes de continuar.",
            "EMBALAJE_CONDICION"
        )

    elif estado == "no_verificable":
        agregar(
            problemas,
            "REVISAR",
            "El estado del embalaje no pudo ser verificado.",
            "Verifica físicamente la carga antes de presentarla.",
            "EMBALAJE_NO_VERIFICADO"
        )


def revisar_tipo_carga(data: dict, problemas: list):
    tipo = limpiar(data.get("tipo_carga"))
    descripcion = normalizar(data.get("descripcion"))

    palabras_dg = [
        "dangerous goods",
        "hazmat",
        "mercancia peligrosa",
        "mercancía peligrosa",
        "bateria de litio",
        "batería de litio",
        "lithium battery",
        "dry ice",
        "hielo seco",
        "flammable",
        "inflamable",
        "corrosive",
        "corrosivo"
    ]

    if tipo == "peligrosa" or any(
        x in descripcion for x in palabras_dg
    ):
        agregar(
            problemas,
            "REVISAR",
            "La carga requiere controles específicos de mercancías peligrosas.",
            "Verifica clasificación, embalaje, marcas, etiquetas y documentación aplicable.",
            "DG"
        )

    if tipo == "animal_vivo":
        agregar(
            problemas,
            "REVISAR",
            "La carga corresponde a un animal vivo.",
            "Verifica requisitos especiales, documentación, contenedor y condiciones de transporte.",
            "LIVE_ANIMAL"
        )

    if tipo == "perecedera":
        agregar(
            problemas,
            "REVISAR",
            "La carga es perecedera.",
            "Verifica conservación, embalaje, temperatura y documentación aplicable.",
            "PERISHABLE"
        )

    if tipo == "farmaceutica":
        agregar(
            problemas,
            "REVISAR",
            "La carga es farmacéutica o relacionada con healthcare.",
            "Verifica condiciones de conservación, documentación y requisitos aplicables.",
            "PHARMA"
        )

    if tipo == "valiosa":
        agregar(
            problemas,
            "REVISAR",
            "La carga está declarada como valiosa.",
            "Verifica requisitos de seguridad, documentación y manejo aplicables.",
            "VAL"
        )


def revisar_awb(data: dict, problemas: list):
    awb = limpiar(data.get("awb"))

    if not awb:
        return

    limpio = re.sub(r"[\s-]", "", awb)

    if not re.fullmatch(r"\d{11}", limpio):
        agregar(
            problemas,
            "CORREGIR",
            "El formato del AWB no parece válido.",
            "Verifica el número de AWB.",
            "AWB_FORMAT"
        )
        return

    if not limpio.startswith("134"):
        agregar(
            problemas,
            "REVISAR",
            "El AWB introducido no comienza con el prefijo 134.",
            "Confirma que el número de AWB corresponda al envío que estás preparando.",
            "AWB_PREFIX"
        )


def comparar_documento(
    data: dict,
    doc_data: dict,
    problemas: list
):
    if not doc_data:
        return

    awb_usuario = re.sub(
        r"[\s-]",
        "",
        limpiar(data.get("awb"))
    )

    awb_doc = re.sub(
        r"[\s-]",
        "",
        limpiar(doc_data.get("awb"))
    )

    if awb_usuario and awb_doc and awb_usuario != awb_doc:
        agregar(
            problemas,
            "CORREGIR",
            f"El AWB no coincide: sistema {awb_usuario} / documento {awb_doc}.",
            "Corrige el dato antes de continuar.",
            "DOC_AWB_MISMATCH"
        )

    piezas_usuario = entero(data.get("piezas"))
    piezas_doc = entero(doc_data.get("piezas"))

    if (
        piezas_usuario > 0
        and piezas_doc > 0
        and piezas_usuario != piezas_doc
    ):
        agregar(
            problemas,
            "CORREGIR",
            f"La cantidad de piezas no coincide: declaradas {piezas_usuario} / documento {piezas_doc}.",
            "Verifica físicamente la carga y corrige el documento o los datos.",
            "DOC_PIECES_MISMATCH"
        )

    peso_usuario = numero(data.get("peso"))
    peso_doc = numero(doc_data.get("peso"))

    if peso_usuario > 0 and peso_doc > 0:
        diferencia = abs(
            peso_usuario - peso_doc
        )

        if diferencia > max(
            0.5,
            peso_usuario * 0.01
        ):
            agregar(
                problemas,
                "CORREGIR",
                f"El peso no coincide: declarado {peso_usuario:g} kg / documento {peso_doc:g} kg.",
                "Verifica el peso real y corrige la información correspondiente.",
                "DOC_WEIGHT_MISMATCH"
            )


def revisar_documentos(
    data: dict,
    documents: list[UploadFile],
    problemas: list
):
    if not documents:
        agregar(
            problemas,
            "REVISAR",
            "No se adjuntaron documentos para esta pre-revisión.",
            "Adjunta los documentos disponibles si el envío requiere documentación.",
            "NO_DOCUMENTS"
        )
        return

    archivos_temporales = []

    try:
        for upload in documents:
            nombre = limpiar(upload.filename)

            if not nombre:
                continue

            if not nombre.lower().endswith(".pdf"):
                agregar(
                    problemas,
                    "CORREGIR",
                    f"El archivo '{nombre}' no es PDF.",
                    "Adjunta un documento PDF válido.",
                    "DOC_FORMAT"
                )
                continue

            path = guardar_temporal(upload)
            archivos_temporales.append(path)

            pdf = extraer_pdf(path)

            if pdf["error"]:
                agregar(
                    problemas,
                    "CORREGIR",
                    f"No se pudo leer el PDF '{nombre}'.",
                    "Reemplaza el archivo por un PDF válido y legible.",
                    "PDF_ERROR"
                )
                continue

            if pdf["vacio"]:
                agregar(
                    problemas,
                    "CORREGIR",
                    f"El PDF '{nombre}' está vacío o no contiene texto extraíble.",
                    "Verifica el documento. Los PDF escaneados requieren revisión visual o OCR futuro.",
                    "PDF_EMPTY"
                )
                continue

            if pdf["ilegible"]:
                agregar(
                    problemas,
                    "CORREGIR",
                    f"El contenido del PDF '{nombre}' no parece legible o contiene caracteres anormales.",
                    "Reemplaza el documento por una copia legible.",
                    "PDF_GARBAGE"
                )
                continue

            extraidos = extraer_campos_pdf(
                pdf["texto"]
            )

            palabras_documentales = [
                "awb",
                "shipper",
                "consignee",
                "pieces",
                "piece",
                "weight",
                "gross",
                "piezas",
                "peso",
                "invoice",
                "commercial invoice",
                "packing list",
                "declaration",
                "certificate",
                "permit",
                "origin",
                "destination",
                "origen",
                "destino"
            ]

            texto_normalizado = normalizar(
                pdf["texto"]
            )

            if not any(
                x in texto_normalizado
                for x in palabras_documentales
            ):
                agregar(
                    problemas,
                    "REVISAR",
                    f"El PDF '{nombre}' contiene texto, pero no se identificó claramente como documentación del envío.",
                    "Confirma que hayas adjuntado el documento correcto.",
                    "PDF_UNRELATED"
                )

            comparar_documento(
                data,
                extraidos,
                problemas
            )

    finally:
        for path in archivos_temporales:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                pass


async def leer_foto_como_evidencia(
    photo: UploadFile
):
    nombre = limpiar(photo.filename)

    if not nombre:
        return None

    extension = Path(nombre).suffix.lower()

    if extension not in EXTENSIONES_IMAGEN:
        return {
            "nombre": nombre,
            "valida": False,
            "error": "Formato de imagen no permitido."
        }

    contenido = await photo.read()

    if not contenido:
        return {
            "nombre": nombre,
            "valida": False,
            "error": "La fotografía está vacía."
        }

    tipo = (
        photo.content_type
        or "image/jpeg"
    )

    if not tipo.startswith("image/"):
        return {
            "nombre": nombre,
            "valida": False,
            "error": "El archivo no es una imagen."
        }

    imagen_b64 = base64.b64encode(
        contenido
    ).decode("ascii")

    return {
        "nombre": nombre,
        "valida": True,
        "tipo": tipo,
        "data": f"data:{tipo};base64,{imagen_b64}"
    }


async def revisar_fotos(
    photos: list[UploadFile],
    piezas: int,
    problemas: list
):
    evidencias = []

    if not photos:
        agregar(
            problemas,
            "REVISAR",
            "No se adjuntaron fotografías de la mercancía.",
            "Si deseas documentar visualmente la carga, agrega fotografías representativas de las piezas.",
            "NO_PHOTOS"
        )
        return evidencias

    cantidad_fotos = len(photos)

    if piezas > 0 and cantidad_fotos < piezas:
        faltan = piezas - cantidad_fotos

        agregar(
            problemas,
            "REVISAR",
            f"Se declararon {piezas} piezas y se recibieron {cantidad_fotos} fotografías; faltan {faltan} fotografías para una evidencia individual de cada pieza.",
            "Agrega fotografías de las piezas que todavía no estén documentadas, cuando sea posible.",
            "PHOTO_COUNT_INCOMPLETE"
        )

    elif piezas > 0 and cantidad_fotos == piezas:
        agregar(
            problemas,
            "REVISAR",
            f"Se recibieron {cantidad_fotos} fotografías para {piezas} piezas.",
            "La evidencia visual está individualizada por cantidad; verifica visualmente que cada fotografía corresponda a una pieza real.",
            "PHOTO_COUNT_MATCH"
        )

    elif piezas > 0 and cantidad_fotos > piezas:
        agregar(
            problemas,
            "REVISAR",
            f"Se recibieron {cantidad_fotos} fotografías para {piezas} piezas.",
            "Puedes conservar fotografías adicionales para documentar embalaje, etiquetas, marcas o diferentes vistas.",
            "PHOTO_COUNT_EXTRA"
        )

    for photo in photos:
        evidencia = await leer_foto_como_evidencia(
            photo
        )

        if not evidencia:
            continue

        if not evidencia["valida"]:
            agregar(
                problemas,
                "CORREGIR",
                f"La fotografía '{evidencia['nombre']}' no es válida.",
                "Reemplaza el archivo por una fotografía JPG, PNG, WEBP o GIF válida.",
                "PHOTO_FORMAT"
            )
            continue

        evidencias.append(evidencia)

    return evidencias


def aplicar_reglas_json(
    data: dict,
    problemas: list
):
    if not RULES:
        return

    matriz = RULES.get(
        "matriz_decision_operacional",
        {}
    )

    if not isinstance(matriz, dict):
        return

    texto = normalizar(
        data.get("descripcion")
    )

    for clave, regla in matriz.items():
        if not isinstance(regla, dict):
            continue

        activar = False

        if clave.lower() in texto.replace(
            " ",
            "_"
        ):
            activar = True

        if activar:
            mensaje = (
                regla.get("mensaje")
                or regla.get("descripcion")
            )

            if mensaje:
                agregar(
                    problemas,
                    "REVISAR",
                    str(mensaje),
                    str(
                        regla.get(
                            "accion",
                            "Verifica los requisitos aplicables."
                        )
                    ),
                    str(
                        regla.get(
                            "codigo",
                            clave
                        )
                    )
                )


def determinar_estado(problemas: list) -> str:
    estados = {
        p.get("estado")
        for p in problemas
    }

    if "CORREGIR" in estados:
        return "CORREGIR"

    if "REVISAR" in estados:
        return "REVISAR"

    return "LISTO"


def resumen_estado(estado: str) -> str:
    if estado == "CORREGIR":
        return (
            "Se encontraron elementos que deben "
            "corregirse antes de continuar."
        )

    if estado == "REVISAR":
        return (
            "La pre-revisión encontró elementos "
            "que requieren confirmación."
        )

    return (
        "No se detectaron inconsistencias básicas "
        "en esta pre-revisión."
    )


def regla_de_oro(estado: str) -> str:
    if estado == "CORREGIR":
        return (
            "NO PRESENTES LA CARGA HASTA CORREGIR "
            "LOS ELEMENTOS INDICADOS."
        )

    if estado == "REVISAR":
        return (
            "CONFIRMA LOS ELEMENTOS INDICADOS "
            "ANTES DE PRESENTAR LA CARGA."
        )

    return (
        "LA CARGA PUEDE CONTINUAR A LA PRESENTACIÓN "
        "PARA LA REVISIÓN CORRESPONDIENTE."
    )


@app.get("/", response_class=HTMLResponse)
async def inicio(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


@app.post("/api/smartcargo/resolver")
async def resolver(
    rol: str = Form(""),
    tipo_carga: str = Form(""),
    descripcion: str = Form(""),
    piezas: str = Form(""),
    peso: str = Form(""),
    largo: str = Form(""),
    ancho: str = Form(""),
    alto: str = Form(""),
    embalaje: str = Form(""),
    shipper: str = Form(""),
    consignee: str = Form(""),
    origen: str = Form(""),
    destino: str = Form(""),
    awb: str = Form(""),
    documents: list[UploadFile] = File(default=[]),
    photos: list[UploadFile] = File(default=[])
):
    data = {
        "rol": rol,
        "tipo_carga": tipo_carga,
        "descripcion": descripcion,
        "piezas": piezas,
        "peso": peso,
        "largo": largo,
        "ancho": ancho,
        "alto": alto,
        "embalaje": embalaje,
        "shipper": shipper,
        "consignee": consignee,
        "origen": origen,
        "destino": destino,
        "awb": awb
    }

    problemas = []

    revisar_basicos(
        data,
        problemas
    )

    revisar_dimensiones(
        data,
        problemas
    )

    revisar_embalaje(
        data,
        problemas
    )

    revisar_tipo_carga(
        data,
        problemas
    )

    revisar_awb(
        data,
        problemas
    )

    aplicar_reglas_json(
        data,
        problemas
    )

    revisar_documentos(
        data,
        documents,
        problemas
    )

    evidencias = await revisar_fotos(
        photos,
        entero(piezas),
        problemas
    )

    vistos = set()
    finales = []

    for problema in problemas:
        clave = (
            problema.get("codigo"),
            problema.get("mensaje")
        )

        if clave not in vistos:
            vistos.add(clave)
            finales.append(problema)

    problemas = finales

    estado = determinar_estado(
        problemas
    )

    return {
        "ok": True,
        "estado": estado,
        "resumen": resumen_estado(estado),
        "problemas": problemas,
        "regla_de_oro": regla_de_oro(estado),
        "rol": ROLES.get(rol, rol),
        "cantidad_piezas": entero(piezas),
        "cantidad_fotos": len(evidencias),
        "evidencia_visual": evidencias,
        "version": "7.0.0"
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "app": "SMARTCARGO",
        "version": "7.0.0"
    }


if __name__ == "__main__":
    import uvicorn

    port = int(
        os.getenv(
            "PORT",
            "8000"
        )
    )

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )
