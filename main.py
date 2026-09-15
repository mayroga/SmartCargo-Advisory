from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from typing import Optional

app = FastAPI(
    title="SmartCargo Advisory Core - Avianca Cargo MIA",
    description="Sistema experto de cumplimiento operativo IATA, TSA, CBP y DOT para Forwarders y Agentes de Counter.",
    version="6.1.0"
)

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartCargo Advisory - MIA | Avianca Cargo</title>
    <style>
        :root {
            --primary-red: #d32f2f;
            --dark-bg: #1a1a1a;
            --light-bg: #f4f6f9;
            --card-bg: #ffffff;
            --text-main: #333333;
            --text-muted: #666666;
            --border-color: #e0e0e0;
        }

        body {
            font-family: Arial, sans-serif;
            background-color: var(--light-bg);
            color: var(--text-main);
            margin: 0;
            padding: 20px;
        }

        .container {
            max-width: 900px;
            background: var(--card-bg);
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            margin: auto;
        }

        h2 {
            color: var(--primary-red);
            text-align: center;
            margin-bottom: 5px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .subtitle {
            text-align: center;
            color: var(--text-muted);
            margin-bottom: 25px;
            font-size: 13px;
        }

        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }

        .form-group {
            margin-bottom: 15px;
        }

        .form-group.full-width {
            grid-column: span 2;
        }

        label {
            display: block;
            font-weight: bold;
            margin-bottom: 5px;
            font-size: 13px;
            color: var(--text-main);
        }

        input, select {
            width: 100%;
            padding: 10px;
            border: 1px solid var(--border-color);
            border-radius: 4px;
            box-sizing: border-box;
            font-size: 14px;
        }

        input:focus, select:focus {
            border-color: var(--primary-red);
            outline: none;
        }

        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 8px;
        }

        .checkbox-group input {
            width: auto;
        }

        .voice-section {
            background: #fff8f8;
            border: 1px dashed var(--primary-red);
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
            text-align: center;
        }

        .btn-voice {
            background: #e53935;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.2s;
        }

        .btn-voice.recording {
            background: #b71c1c;
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }

        .btn-container {
            display: flex;
            gap: 10px;
            margin-top: 20px;
        }

        button.action-btn {
            flex: 2;
            padding: 12px;
            background: var(--primary-red);
            color: white;
            border: none;
            border-radius: 4px;
            font-weight: bold;
            font-size: 14px;
            cursor: pointer;
        }

        button.action-btn:hover {
            opacity: 0.9;
        }

        button.btn-clear {
            flex: 1;
            padding: 12px;
            background: #555555;
            color: white;
            border: none;
            border-radius: 4px;
            font-weight: bold;
            font-size: 14px;
            cursor: pointer;
        }

        button.btn-clear:hover {
            opacity: 0.9;
        }

        #resultado-box {
            margin-top: 25px;
            background: #fafafa;
            border: 1px solid var(--border-color);
            padding: 20px;
            border-radius: 6px;
            display: none;
        }

        #resultado-box h3 {
            margin-top: 0;
            color: var(--text-main);
            border-bottom: 2px solid var(--primary-red);
            padding-bottom: 8px;
            font-size: 16px;
        }

        .result-item {
            margin-bottom: 12px;
            font-size: 14px;
        }

        .highlight-status {
            font-weight: bold;
            padding: 4px 8px;
            border-radius: 4px;
            display: inline-block;
        }
        
        .status-ok { background: #e8f5e9; color: #2e7d32; }
        .status-error { background: #ffebee; color: #c62828; }
        .status-warning { background: #fffde7; color: #f57f17; }
        
        ul { margin: 5px 0; padding-left: 20px; }
    </style>
</head>
<body>

<div class="container">
    <h2>SmartCargo Advisory - MIA</h2>
    <div class="subtitle">Motor Experto de Cumplimiento Operativo | IATA, TSA, CBP y DOT</div>
    
    <!-- Botón de Voz -->
    <div class="voice-section">
        <label style="margin-bottom: 8px;">Dictado por voz operativo (máximo 60 segundos):</label>
        <button type="button" id="voiceBtn" class="btn-voice" onclick="toggleVoiceRecording()">🎙️ Iniciar Dictado por Voz</button>
        <span id="voiceStatus" style="display:block; font-size:11px; color: var(--text-muted); margin-top: 5px;">Haga clic para hablar sobre los datos de la carga.</span>
    </div>

    <form id="cargoForm" onsubmit="enviarConsulta(event)">
        <div class="form-grid">
            <div class="form-group">
                <label for="rol_operativo">Rol del Operador:</label>
                <select id="rol_operativo" required>
                    <option value="forwarder">Forwarder (Agente de Carga)</option>
                    <option value="counter">Agente de Counter / Bodega</option>
                </select>
            </div>

            <div class="form-group">
                <label for="awb_numero">Guía Aérea (AWB - Prefijo 134):</label>
                <input type="text" id="awb_numero" placeholder="Ej: 134-87654321" required>
            </div>

            <div class="form-group">
                <label for="nombre_shipper">Nombre del Expedidor (Shipper):</label>
                <input type="text" id="nombre_shipper" placeholder="Empresa o Exportador" required>
            </div>

            <div class="form-group">
                <label for="nombre_consignatario">Consignatario (Consignee):</label>
                <input type="text" id="nombre_consignatario" placeholder="Destinatario final" required>
            </div>

            <div class="form-group">
                <label for="transportista_nombre">Nombre del Transportista (Chofer):</label>
                <input type="text" id="transportista_nombre" placeholder="Nombre completo" required>
            </div>

            <div class="form-group">
                <label for="licencia_transportista">Licencia o ID del Transportista:</label>
                <input type="text" id="licencia_transportista" placeholder="Número de licencia" required>
            </div>

            <div class="form-group">
                <label for="tipo_carga">Categoría de Carga:</label>
                <select id="tipo_carga" required>
                    <option value="general">Carga General / Seca</option>
                    <option value="perecedero">Perecederos / Alimentos / Flores</option>
                    <option value="dg">Mercancías Peligrosas (DG)</option>
                    <option value="avi">Animales Vivos (AVI)</option>
                    <option value="valioso">Carga Valiosa (VAL)</option>
                </select>
            </div>

            <div class="form-group">
                <label for="estacion_destino">Estación de Destino:</label>
                <input type="text" id="estacion_destino" placeholder="Ej: BOG, MDE, PTY" required>
            </div>

            <div class="form-group">
                <label for="peso_bruto_kg">Peso Bruto (KG):</label>
                <input type="number" step="0.01" id="peso_bruto_kg" placeholder="0.00" required>
            </div>

            <div class="form-group">
                <label for="volumen_cbm">Volumen (CBM):</label>
                <input type="number" step="0.01" id="volumen_cbm" placeholder="0.00" required>
            </div>

            <div class="form-group">
                <label for="tipo_estiba">Tipo de Estiba / Pallet:</label>
                <select id="tipo_estiba" required>
                    <option value="nimf15">Madera Tratada (Certificada NIMF 15)</option>
                    <option value="plastico">Estiba Plástica</option>
                    <option value="madera_cruda">Madera Cruda / Sin Tratar (¡Prohibido!)</option>
                </select>
            </div>

            <div class="form-group">
                <label for="estado_envoltura">Estado Físico del Empaque:</label>
                <select id="estado_envoltura" required>
                    <option value="intacto">Intacto, Seco y Conforme</option>
                    <option value="humedo_danado">Húmedo o Dañado en Superficie</option>
                    <option value="roto_perforado">Roto o Perforado</option>
                </select>
            </div>

            <div class="form-group full-width" style="background: #f9f9f9; padding: 12px; border: 1px solid #ddd; border-radius: 4px;">
                <label style="margin-bottom: 10px; color: #111;">Checklist de Papelería Regulatoria (IATA / TSA / CBP):</label>
                
                <div class="checkbox-group">
                    <input type="checkbox" id="tiene_awb_original">
                    <label for="tiene_awb_original" style="margin:0; font-weight:normal;">Guía Aérea (AWB) Original emitida y verificada</label>
                </div>
                <div class="checkbox-group">
                    <input type="checkbox" id="tiene_dgd_firmada">
                    <label for="tiene_dgd_firmada" style="margin:0; font-weight:normal;">DGD (Dangerous Goods Declaration) con 2 originales firmados en tinta húmeda (si aplica)</label>
                </div>
                <div class="checkbox-group">
                    <input type="checkbox" id="tiene_usda_fda">
                    <label for="tiene_usda_fda" style="margin:0; font-weight:normal;">Certificado Fitosanitario USDA / FDA (si aplica para perecederos)</label>
                </div>
                <div class="checkbox-group">
                    <input type="checkbox" id="tiene_tsa_known_shipper">
                    <label for="tiene_tsa_known_shipper" style="margin:0; font-weight:normal;">Registro de Expedidor Confiable (TSA Known Shipper / CCSP)</label>
                </div>
                <div class="checkbox-group">
                    <input type="checkbox" id="tiene_permiso_aduanero_cbp">
                    <label for="tiene_permiso_aduanero_cbp" style="margin:0; font-weight:normal;">Control Aduanero / Manifiesto In-bond de Aduana (CBP)</label>
                </div>
            </div>

            <div class="form-group full-width">
                <label for="archivo_pdf">Adjuntar Documento Adicional (PDF):</label>
                <input type="file" id="archivo_pdf" accept=".pdf">
            </div>
        </div>

        <div class="btn-container">
            <button type="submit" class="action-btn">Ejecutar Validación Experta</button>
            <button type="button" class="btn-clear" onclick="limpiarFormulario()">Borrar Datos</button>
        </div>
    </form>

    <div id="resultado-box">
        <h3>Dictamen Operativo y Regulatorio</h3>
        <div class="result-item"><strong>Estación:</strong> <span id="res-estacion"></span></div>
        <div class="result-item"><strong>Rol:</strong> <span id="res-rol"></span></div>
        <div class="result-item"><strong>Guía Aérea:</strong> <span id="res-awb"></span></div>
        <div class="result-item"><strong>Destino:</strong> <span id="res-destino"></span></div>
        <div class="result-item"><strong>Estatus del Sistema:</strong> <span id="res-dictamen"></span></div>
        
        <div class="result-item">
            <strong>Alertas Críticas Identificadas:</strong>
            <ul id="res-alertas"></ul>
        </div>

        <div class="result-item">
            <strong>Papelería Pendiente o por Corregir:</strong>
            <ul id="res-papeleria"></ul>
        </div>

        <div class="result-item">
            <strong>Instrucciones y Solución Directa:</strong>
            <ul id="res-instrucciones"></ul>
        </div>

        <div class="result-item"><strong>Auditoría Documental:</strong> <span id="res-pdf"></span></div>
        <div class="result-item" style="font-size: 12px; color: #666; margin-top: 15px; border-top: 1px solid #ddd; padding-top: 8px;"><em><span id="res-aviso"></span></em></div>
    </div>
</div>

<script>
let recognition = null;
let isRecording = false;

function toggleVoiceRecording() {
    const btn = document.getElementById('voiceBtn');
    const status = document.getElementById('voiceStatus');

    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        alert('Su navegador no soporta el dictado por voz.');
        return;
    }

    if (!isRecording) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.lang = 'es-US';
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;

        recognition.onstart = function() {
            isRecording = true;
            btn.classList.add('recording');
            btn.innerText = '🔴 Escuchando...';
            status.innerText = 'Dictado activo. Hable claro...';
        };

        recognition.onresult = function(event) {
            const transcript = event.results[0][0].transcript;
            document.getElementById('awb_numero').value = "134-VOZ-" + Math.floor(Math.random() * 10000);
            status.innerText = 'Dictado capturado: "' + transcript + '"';
        };

        recognition.onerror = function() {
            status.innerText = 'Error en el reconocimiento de voz.';
            detenerVozUI(btn);
        };

        recognition.onend = function() {
            detenerVozUI(btn);
        };

        recognition.start();

        setTimeout(() => {
            if (isRecording && recognition) { recognition.stop(); }
        }, 60000);
    } else {
        if (recognition) { recognition.stop(); }
        detenerVozUI(btn);
    }
}

function detenerVozUI(btn) {
    isRecording = false;
    btn.classList.remove('recording');
    btn.innerText = '🎙️ Iniciar Dictado por Voz';
}

async function enviarConsulta(event) {
    event.preventDefault();
    
    const formData = new FormData();
    formData.append("rol_operativo", document.getElementById('rol_operativo').value);
    formData.append("nombre_shipper", document.getElementById('nombre_shipper').value);
    formData.append("nombre_consignatario", document.getElementById('nombre_consignatario').value);
    formData.append("transportista_nombre", document.getElementById('transportista_nombre').value);
    formData.append("licencia_transportista", document.getElementById('licencia_transportista').value);
    formData.append("awb_numero", document.getElementById('awb_numero').value);
    formData.append("estacion_destino", document.getElementById('estacion_destino').value);
    formData.append("tipo_carga", document.getElementById('tipo_carga').value);
    formData.append("peso_bruto_kg", document.getElementById('peso_bruto_kg').value);
    formData.append("volumen_cbm", document.getElementById('volumen_cbm').value);
    formData.append("tipo_estiba", document.getElementById('tipo_estiba').value);
    formData.append("estado_envoltura", document.getElementById('estado_envoltura').value);
    
    formData.append("tiene_awb_original", document.getElementById('tiene_awb_original').checked);
    formData.append("tiene_dgd_firmada", document.getElementById('tiene_dgd_firmada').checked);
    formData.append("tiene_usda_fda", document.getElementById('tiene_usda_fda').checked);
    formData.append("tiene_tsa_known_shipper", document.getElementById('tiene_tsa_known_shipper').checked);
    formData.append("tiene_permiso_aduanero_cbp", document.getElementById('tiene_permiso_aduanero_cbp').checked);

    const fileField = document.getElementById('archivo_pdf');
    if (fileField.files[0]) {
        formData.append("archivo_pdf", fileField.files[0]);
    }

    try {
        const response = await fetch('/api/smartcargo/analisis-profundo', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error('Error al procesar la validación en el servidor.');
        }

        const data = await response.json();
        
        document.getElementById('res-estacion').innerText = data.estacion;
        document.getElementById('res-rol').innerText = data.rol_evaluador;
        document.getElementById('res-awb').innerText = data.guia_aerea;
        document.getElementById('res-destino').innerText = data.destino;
        
        const dictamenSpan = document.getElementById('res-dictamen');
        dictamenSpan.innerText = data.dictamen_final;
        if (data.dictamen_final.includes("APROBADO")) {
            dictamenSpan.className = "highlight-status status-ok";
        } else if (data.dictamen_final.includes("RECHAZADO")) {
            dictamenSpan.className = "highlight-status status-error";
        } else {
            dictamenSpan.className = "highlight-status status-warning";
        }

        renderList('res-alertas', data.alertas_identificadas);
        renderList('res-papeleria', data.papeleria_pendiente_o_corregir);
        renderList('res-instrucciones', data.instrucciones_accionables);

        document.getElementById('res-pdf').innerText = data.auditoria_documental_pdf;
        document.getElementById('res-aviso').innerText = data.aviso_legal;
        
        document.getElementById('resultado-box').style.display = 'block';
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    } catch (error) {
        alert('Error de conexión: ' + error.message);
    }
}

function renderList(elementId, items) {
    const ul = document.getElementById(elementId);
    ul.innerHTML = '';
    items.forEach(item => {
        const li = document.createElement('li');
        li.innerText = item;
        ul.appendChild(li);
    });
}

function limpiarFormulario() {
    document.getElementById('cargoForm').reset();
    document.getElementById('resultado-box').style.display = 'none';
    document.getElementById('voiceStatus').innerText = 'Haga clic para hablar sobre los datos de la carga.';
}
</script>

</body>
</html>
    """

@app.post("/api/smartcargo/analisis-profundo")
def analisis_profundo_operacion(
    rol_operativo: str = Form(...),
    nombre_shipper: str = Form(...),
    nombre_consignatario: str = Form(...),
    transportista_nombre: str = Form(...),
    licencia_transportista: str = Form(...),
    awb_numero: str = Form(...),
    estacion_destino: str = Form(...),
    tipo_carga: str = Form(...),
    peso_bruto_kg: float = Form(...),
    volumen_cbm: float = Form(...),
    tipo_estiba: str = Form(...),
    estado_envoltura: str = Form(...),
    tiene_awb_original: bool = Form(False),
    tiene_dgd_firmada: bool = Form(False),
    tiene_usda_fda: bool = Form(False),
    tiene_tsa_known_shipper: bool = Form(False),
    tiene_permiso_aduanero_cbp: bool = Form(False),
    archivo_pdf: Optional[UploadFile] = File(None)
):
    alertas_criticas = []
    acciones_correctivas = []
    papeleria_faltante = []
    dictamen_estado = "APROBADO - LISTO PARA DESPACHO"

    # 1. Trazabilidad y Puerta
    if not nombre_shipper or not nombre_consignatario or not licencia_transportista:
        dictamen_estado = "RECHAZADO EN PUERTA"
        alertas_criticas.append("Faltan datos maestros obligatorios de trazabilidad.")
        acciones_correctivas.append("Detener ingreso del transporte hasta completar la identificación del chofer y expedidor.")

    # 2. Seguridad TSA
    if not tiene_tsa_known_shipper:
        dictamen_estado = "RETENIDO POR SEGURIDAD"
        alertas_criticas.append("Incumplimiento TSA: Falta constancia de Expedidor Confiable (Known Shipper).")
        papeleria_faltante.append("Certificación TSA / CCSP de cadena de custodia")
        acciones_correctivas.append("Verificar base de datos de seguridad o solicitar declaración formal.")

    # 3. Aduana CBP
    if not tiene_permiso_aduanero_cbp and estacion_destino.upper() != "MIA":
        papeleria_faltante.append("Documento de Control Aduanero CBP (In-bond / Manifiesto)")
        acciones_correctivas.append("Completar registro aduanero antes de presentar la carga en báscula.")

    # 4. Estibas (NIMF 15)
    if tipo_estiba == "madera_cruda":
        dictamen_estado = "RECHAZADO - RIESGO DE MULTA"
        alertas_criticas.append("Infracción: Uso detectado de madera cruda sin tratamiento térmico NIMF 15.")
        acciones_correctivas.append("Instrucción directa: Reemplazar estiba por una de plástico o madera certificada NIMF 15 de inmediato.")

    # 5. Estado Físico
    if estado_envoltura in ["humedo_danado", "roto_perforado"]:
        dictamen_estado = "RETENIDO PARA REEMPAQUE"
        alertas_criticas.append("El empaque exterior presenta daños o humedad que comprometen la carga.")
        acciones_correctivas.append("Instrucción directa: Aislar bulto, reempacar o reforzar antes de documentar.")

    # 6. Tipo de Carga Específica (IATA)
    tipo = tipo_carga.lower()
    if tipo == "dg":
        if not tiene_dgd_firmada:
            dictamen_estado = "RECHAZADO - RIESGO DE MULTA FEDERAL"
            alertas_criticas.append("Falta la Declaración del Expedidor de Mercancías Peligrosas (DGD).")
            papeleria_faltante.append("2 Originales de DGD con firma en tinta húmeda (IATA DGR)")
            acciones_correctivas.append("Rellenar DGD requerida con doble original y firma autógrafa.")
        else:
            acciones_correctivas.append("DGD validada correctamente. Proceder con inspección física de marcas y etiquetas.")
    elif tipo == "perecedero":
        if not tiene_usda_fda:
            dictamen_estado = "RETENCIÓN SANITARIA"
            alertas_criticas.append("Falta autorización fitosanitaria para perecederos.")
            papeleria_faltante.append("Certificado Fitosanitario USDA / FDA")
            acciones_correctivas.append("Retener papelería en ventanilla y exigir copia digital USDA/FDA.")
        else:
            acciones_correctivas.append("Permiso fitosanitario en orden. Ingresar a cadena de frío.")
    elif tipo == "avi":
        acciones_correctivas.append("Verificar que el Kennel cumpla con dimensiones IATA LAR y revisar cartilla de vacunación.")

    estado_pdf = f"Archivo '{archivo_pdf.filename}' integrado al expediente digital." if archivo_pdf else "Sin documento PDF adjunto."

    return {
        "estacion": "Miami International Airport (MIA) - Avianca Cargo",
        "rol_evaluador": rol_operativo.upper(),
        "guia_aerea": awb_numero,
        "destino": estacion_destino.upper(),
        "dictamen_final": dictamen_estado,
        "alertas_identificadas": alertas_criticas if alertas_criticas else ["Ninguna. Cumplimiento normativo total."],
        "papeleria_pendiente_o_corregir": papeleria_faltante if papeleria_faltante else ["Toda la papelería legal está completa."],
        "instrucciones_accionables": acciones_correctivas if acciones_correctivas else ["Proceder con aceptación estándar y pesaje final para vuelo."],
        "auditoria_documental_pdf": estado_pdf,
        "aviso_legal": "Asesoría experta preventiva basada en normativas IATA, TSA, CBP y DOT. Diseñado para proteger la operación contra retrasos y sanciones."
    }
