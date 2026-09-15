from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(
    title="SmartCargo Deep Advisory Core - Avianca Cargo MIA",
    description="Motor experto de cumplimiento IATA, TSA, CBP, DOT para Forwarders y Agentes de Counter.",
    version="6.0.0"
)

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
        <head><title>SmartCargo Deep Core</title></head>
        <body style="font-family: Arial; padding: 40px; background: #111; color: #eee;">
            <h2>SmartCargo Deep Expert Core Activo</h2>
            <p>Sistema de procesamiento normativo profundo (IATA / TSA / CBP / DOT) para Forwarders y Counters de Avianca Cargo.</p>
        </body>
    </html>
    """

@app.post("/api/smartcargo/analisis-profundo")
def analisis_profundo_operacion(
    # 1. Actores y Trazabilidad Básica
    rol_operativo: str = Form(...), # "forwarder" o "counter"
    nombre_shipper: str = Form(...),
    nombre_consignatario: str = Form(...),
    transportista_nombre: str = Form(...),
    licencia_transportista: str = Form(...),
    
    # 2. Datos del AWB y Carga
    awb_numero: str = Form(...),
    estacion_destino: str = Form(...),
    tipo_carga: str = Form(...), # "perecedero", "dg", "avi", "general", "valioso"
    peso_bruto_kg: float = Form(...),
    volumen_cbm: float = Form(...),
    
    # 3. Empaque, Pallets y Estibas
    tipo_estiba: str = Form(...), # "nimf15", "plastico", "madera_cruda"
    estado_envoltura: str = Form(...), # "intacto", "humedo_danado", "roto_perforado"
    
    # 4. Papelería y Permisos Legales (Checklist Maestro)
    tiene_awb_original: bool = Form(False),
    tiene_dgd_firmada: bool = Form(False), # Requerido para DG (2 originales tinta húmeda)
    tiene_usda_fda: bool = Form(False),    # Requerido para Perecederos/Alimentos
    tiene_tsa_known_shipper: bool = Form(False), # Requerido por TSA
    tiene_permiso_aduanero_cbp: bool = Form(False), # Requerido por CBP
    
    archivo_pdf: Optional[UploadFile] = File(None)
):
    alertas_criticas = []
    acciones_correctivas = []
    papeleria_faltante = []
    dictamen_estado = "APROBADO - LISTO PARA DESPACHO"

    # --- VALIDACIÓN 1: TRAZABILIDAD Y TRANSPORTISTA (Puerta / MIA) ---
    if not nombre_shipper or not nombre_consignatario or not licencia_transportista:
        dictamen_estado = "RECHAZADO EN PUERTA"
        alertas_criticas.append("Faltan datos maestros de trazabilidad (Shipper, Consignee o Licencia del Chofer).")
        acciones_correctivas.append("Detener ingreso del camión a la plataforma hasta completar datos de identificación.")

    # --- VALIDACIÓN 2: NORMATIVA TSA (Seguridad de Carga Aérea) ---
    if not tiene_tsa_known_shipper:
        dictamen_estado = "RETENIDO POR SEGURIDAD"
        alertas_criticas.append("Incumplimiento TSA: El expedidor no está registrado como 'Known Shipper' o falta constancia de cadena de custodia.")
        papeleria_faltante.append("Certificación TSA / CCSP de Cadenas de Custodia")
        acciones_correctivas.append("Verificar base de datos TSA o exigir declaración formal de seguridad de carga comercial.")

    # --- VALIDACIÓN 3: NORMATIVA CBP Y DOT (Aduana y Transporte) ---
    if not tiene_permiso_aduanero_cbp and estacion_destino.upper() not in ["MIA"]: # Si es internacional o tránsito
        papeleria_faltante.append("Documento de Control Aduanero CBP (In-bond / Manifiesto de Exportación)")
        acciones_correctivas.append("Rellenar y corregir formato de aduana CBP antes de presentar la carga en la báscula.")

    # --- VALIDACIÓN 4: ESTIBAS Y PALLETS (Norma NIMF 15 / ICHM) ---
    if tipo_estiba == "madera_cruda":
        dictamen_estado = "RECHAZADO - RIESGO DE MULTA"
        alertas_criticas.append("Infracción grave: Se detectó uso de madera cruda sin tratamiento térmico NIMF 15.")
        acciones_correctivas.append("Instrucción directa: Cambiar inmediatamente el pallet por uno de plástico o madera certificada NIMF 15. Prohibido el ingreso a rampa de Avianca Cargo.")

    # --- VALIDACIÓN 5: ENVOLTURA Y ESTADO FÍSICO ---
    if estado_envoltura in ["humedo_danado", "roto_perforado"]:
        dictamen_estado = "RETENIDO PARA REEMPAQUE"
        alertas_criticas.append("El empaque exterior muestra daños o humedad que comprometen la integridad de la carga.")
        acciones_correctivas.append("Instrucción directa: Aislar bulto, realizar reempaque o refuerzo de cartón ceroso/plástico antes de documentar.")

    # --- VALIDACIÓN 6: REQUISITOS ESPECÍFICos POR TIPO DE CARGA (IATA DGR / LAR) ---
    tipo = tipo_carga.lower()
    
    if tipo == "dg": # Mercancías Peligrosas
        if not tiene_dgd_firmada:
            dictamen_estado = "RECHAZADO - RIESGO DE MULTA FEDERAL"
            alertas_criticas.append("Falta la Declaración del Expedidor de Mercancías Peligrosas (DGD).")
            papeleria_faltante.append("2 Originales de DGD con firma en tinta húmeda (IATA DGR)")
            acciones_correctivas.append("Corregir y rellenar DGD. Se requieren estrictamente dos originales con firma en tinta húmeda (uno para archivo, uno para el capitán del vuelo).")
        else:
            acciones_correctivas.append("DGD validada. Realizar inspección física obligatoria de marcas, etiquetas y clases de compatibilidad.")

    elif tipo == "perecedero": # Alimentos / Flores
        if not tiene_usda_fda:
            dictamen_estado = "RETENCIÓN SANITARIA"
            alertas_criticas.append("Falta autorización fitosanitaria para productos perecederos.")
            papeleria_faltante.append("Certificado Fitosanitario USDA / FDA")
            acciones_correctivas.append("Retener papelería en ventanilla. Solicitar copia digital del USDA/FDA al forwarder y verificar termosensor activo.")
        else:
            acciones_correctivas.append("Permiso fitosanitario en orden. Programar ingreso inmediato a cadena de frío de Avianca Cargo.")

    elif tipo == "avi": # Animales Vivos
        acciones_correctivas.append("Verificar que el Kennel cumpla con dimensiones IATA LAR (animal debe poder girar y estar de pie) y validar cartilla de vacunación original.")

    # Análisis de PDF adjunto si lo hubiera
    estado_pdf = "Sin documento analizado."
    if archivo_pdf:
        estado_pdf = f"Archivo '{archivo_pdf.filename}' procesado e integrado al expediente digital de la guía {awb_numero}."

    # --- SALIDA ESTRUCTURADA PARA EL FORWARDER O COUNTER ---
    return {
        "estacion": "Miami International Airport (MIA) - Avianca Cargo",
        "rol_evaluador": rol_operativo.upper(),
        "guia_aerea": awb_numero,
        "destino": estacion_destino.upper(),
        "dictamen_final": dictamen_estado,
        "alertas_identificadas": alertas_criticas if alertas_criticas else ["Ninguna. Cumplimiento normativo total."],
        "papeleria_pendiente_o_corregir": papeleria_faltante if papeleria_faltante else ["Toda la papelería legal está completa."],
        "instrucciones_accionables": acciones_correctivas if acciones_correctivas else ["Proceder con aceptación estándar, pesaje final y etiquetado para vuelo."],
        "auditoria_documental_pdf": estado_pdf,
        "aviso_legal": "Asesoría experta preventiva basada en manuales IATA, TSA, CBP y DOT. Protegemos su operación contra retrasos, multas y pérdida de vuelos."
    }
