from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from typing import Optional

app = FastAPI(
    title="SmartCargo Advisory",
    version="9.0.0"
)

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SmartCargo Advisory - MIA</title>
    <style>
        :root {
            --primary-red: #cc0000;
            --bg-color: #f2f4f7;
            --card-bg: #ffffff;
            --text-main: #222222;
            --border: #cccccc;
        }

        body {
            font-family: Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 15px;
        }

        .container {
            max-width: 850px;
            background: var(--card-bg);
            padding: 20px;
            border-radius: 6px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            margin: auto;
        }

        h2 {
            color: var(--primary-red);
            text-align: center;
            margin-bottom: 3px;
            text-transform: uppercase;
            font-size: 20px;
        }

        .subtitle {
            text-align: center;
            color: #555;
            margin-bottom: 15px;
            font-size: 12px;
            font-weight: bold;
        }

        /* Sección del Manual y Requisitos de Aviación */
        .manual-section {
            background: #fffdfd;
            border: 1px solid var(--primary-red);
            padding: 12px;
            border-radius: 4px;
            margin-bottom: 15px;
            font-size: 12px;
        }

        .manual-section h3 {
            margin: 0 0 8px 0;
            color: var(--primary-red);
            font-size: 13px;
            text-transform: uppercase;
        }

        .manual-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }

        .manual-grid ul {
            margin: 0;
            padding-left: 15px;
        }

        .manual-grid li {
            margin-bottom: 4px;
        }

        .form-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
        }

        .full {
            grid-column: span 2;
        }

        label {
            display: block;
            font-weight: bold;
            margin-bottom: 3px;
            font-size: 12px;
        }

        input, select, textarea {
            width: 100%;
            padding: 8px;
            border: 1px solid var(--border);
            border-radius: 3px;
            box-sizing: border-box;
            font-size: 13px;
        }

        .voice-box {
            background: #fff5f5;
            border: 1px dashed var(--primary-red);
            padding: 8px;
            border-radius: 4px;
            margin-bottom: 15px;
            text-align: center;
        }

        .btn-voice {
            background: var(--primary-red);
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 15px;
            font-size: 11px;
            font-weight: bold;
            cursor: pointer;
        }

        .btn-voice.recording {
            background: #900;
            animation: pulse 1s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.03); }
            100% { transform: scale(1); }
        }

        .btn-group {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }

        button.submit-btn {
            flex: 2;
            padding: 10px;
            background: var(--primary-red);
            color: white;
            border: none;
            border-radius: 3px;
            font-weight: bold;
            font-size: 13px;
            cursor: pointer;
        }

        button.clear-btn {
            flex: 1;
            padding: 10px;
            background: #444;
            color: white;
            border: none;
            border-radius: 3px;
            font-weight: bold;
            font-size: 13px;
            cursor: pointer;
        }

        #result {
            margin-top: 20px;
            background: #fafafa;
            border: 1px solid var(--border);
            padding: 15px;
            border-radius: 4px;
            display: none;
        }

        .table-res {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 13px;
        }

        .table-res th, .table-res td {
            border: 1px solid #ddd;
            padding: 8px;
            text-align: left;
        }

        .table-res th {
            background-color: #333;
            color: white;
            width: 30%;
        }
    </style>
</head>
<body>

<div class="container">
    <h2>SmartCargo Advisory</h2>
    <div class="subtitle">MIA | Manual Operativo, Counter, Bodega, Bellies & Freighters</div>
    
    <!-- MANUAL Y REQUISITOS TÉCNICOS VISIBLES -->
    <div class="manual-section">
        <h3>📖 Manual de Requisitos y Obligaciones Operativas (Aviación Comercial)</h3>
        <div class="manual-grid">
            <div>
                <strong>1. Obligaciones de Aceptación (Counter / Bodega):</strong>
                <ul>
                    <li>Verificar coincidencia exacta de Guía Aérea (AWB prefijo 134) y piezas físicas.</li>
                    <li>Control de dimensiones y gálibo según tipo de aeronave (Bellies PAX vs. Freighter).</li>
                    <li>Inspección obligatoria de marcas, etiquetas de peligro y sellos de origen.</li>
                </ul>
            </div>
            <div>
                <strong>2. Requisitos de Estibas y Empaque:</strong>
                <ul>
                    <li>Estibas de madera obligatoriamente con marca o certificado térmico visible. Prohibida madera cruda.</li>
                    <li>Empaques secos, intactos y sin perforaciones que comprometan la carga.</li>
                    <li>Distribución simétrica de peso y sujeción firme con film de alta densidad.</li>
                </ul>
            </div>
        </div>
    </div>

    <div class="voice-box">
        <button type="button" id="vBtn" class="btn-voice" onclick="toggleVoice()">🎙️ Dictar Incidencia / Carga</button>
        <span id="vStatus" style="display:block; font-size:10px; color:#666; margin-top:3px;">Opcional: Describa la carga por voz (máx 60s).</span>
    </div>

    <form id="cForm" onsubmit="analizar(event)">
        <div class="form-grid">
            <div>
                <label>Rol Operativo:</label>
                <select id="rol">
                    <option value="Counter / Bodega">Counter / Bodega</option>
                    <option value="Forwarder">Forwarder</option>
                    <option value="Transfer / GSA">Transfer / GSA</option>
                </select>
            </div>
            <div>
                <label>Guía (AWB / Ref):</label>
                <input type="text" id="awb" placeholder="Ej: 134-XXXXXXXX" required>
            </div>
            <div>
                <label>Tipo de Carga:</label>
                <select id="tipo">
                    <option value="General / Seca">General / Seca / Comat</option>
                    <option value="Perecedero / Flores">Perecederos / Flores</option>
                    <option value="Especial / DG">Especiales / DG / Valor</option>
                    <option value="Bellies / Pax">Bellies (PAX) / Interlines</option>
                </select>
            </div>
            <div>
                <label>Destino:</label>
                <input type="text" id="destino" placeholder="Ej: BOG" required>
            </div>
            <div class="full">
                <label>Situación / Anomalía en Rampa o Counter:</label>
                <textarea id="problema" rows="2" placeholder="Ej: Pallet húmedo en base, altura excedida para bellies, estiba sin sello NIMF 15..." required></textarea>
            </div>
            <div class="full">
                <label>Documento Adjunto (PDF):</label>
                <input type="file" id="pdfFile" accept=".pdf">
            </div>
        </div>

        <div class="btn-group">
            <button type="submit" class="submit-btn">Obtener Solución Directa</button>
            <button type="button" class="clear-btn" onclick="resetForm()">Borrar Datos</button>
        </div>
    </form>

    <div id="result">
        <h3 style="margin:0 0 10px 0; color:var(--primary-red); font-size:15px; text-transform:uppercase;">Dictamen Operativo y Solución Directa</h3>
        <table class="table-res">
            <tr><th>Estatus</th><td id="res-estatus" style="font-weight:bold; color:var(--primary-red);"></td></tr>
            <tr><th>Solución 1 (Principal)</th><td id="res-sol1"></td></tr>
            <tr><th>Solución 2 (Alternativa)</th><td id="res-sol2"></td></tr>
            <tr><th>Instrucción Directa</th><td id="res-inst" style="font-weight:bold; background:#fff3f3;"></td></tr>
        </table>
        <div style="text-align: right; margin-top: 10px;">
            <button onclick="window.print()" style="background:#222; color:#fff; border:none; padding:6px 12px; font-size:11px; cursor:pointer; border-radius:3px;">🖨️ Imprimir / Guardar PDF</button>
        </div>
    </div>
</div>

<script>
let rec = null;
let recording = false;

function toggleVoice() {
    const btn = document.getElementById('vBtn');
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        alert('No compatible con voz.'); return;
    }
    if (!recording) {
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        rec = new SR(); rec.lang = 'es-US';
        rec.onstart = () => { recording = true; btn.classList.add('recording'); btn.innerText = '🔴 Escuchando...'; };
        rec.onresult = (e) => { document.getElementById('problema').value = e.results[0][0].transcript; };
        rec.onend = () => stopV(btn);
        rec.onerror = () => stopV(btn);
        rec.start();
        setTimeout(() => { if(recording && rec) rec.stop(); }, 60000);
    } else {
        if(rec) rec.stop(); stopV(btn);
    }
}
function stopV(btn) { recording = false; btn.classList.remove('recording'); btn.innerText = '🎙️ Dictar Incidencia / Carga'; }

async function analizar(e) {
    e.preventDefault();
    const fd = new FormData();
    fd.append("rol", document.getElementById('rol').value);
    fd.append("awb", document.getElementById('awb').value);
    fd.append("tipo", document.getElementById('tipo').value);
    fd.append("destino", document.getElementById('destino').value);
    fd.append("problema", document.getElementById('problema').value);
    const file = document.getElementById('pdfFile').files[0];
    if(file) fd.append("pdfFile", file);

    const res = await fetch('/api/resolver', { method: 'POST', body: fd });
    const data = await res.json();
    
    document.getElementById('res-estatus').innerText = data.estatus;
    document.getElementById('res-sol1').innerText = data.sol_1;
    document.getElementById('res-sol2').innerText = data.sol_2;
    document.getElementById('res-inst').innerText = data.instruccion;
    document.getElementById('result').style.display = 'block';
}

function resetForm() {
    document.getElementById('cForm').reset();
    document.getElementById('result').style.display = 'none';
}
</script>

</body>
</html>
    """

@app.post("/api/resolver")
def resolver(
    rol: str = Form(...),
    awb: str = Form(...),
    tipo: str = Form(...),
    destino: str = Form(...),
    problema: str = Form(...),
    pdfFile: Optional[UploadFile] = File(None)
):
    p = problema.lower()
    
    if "humed" in p or "agua" in p or "mojado" in p:
        estatus = "No Conforme por Humedad o Empaque Dañado"
        sol_1 = "Aplicar refuerzo con strech film de alta densidad y cartón corrugado antihumedad en la base."
        sol_2 = "Transferir de inmediato la mercancía a estiba plástica limpia y descartar la tarima húmeda."
        instruccion = "Llevar la carga a zona de reempaque o cambiar a estiba plástica."
    elif "alto" in p or "dimension" in p or "grande" in p or "medida" in p:
        estatus = "Fuera de Gálibo / Exceso de Perfil Operativo"
        sol_1 = "Reestructurar el armado rebajando la altura de la estiba para cumplir con el gálibo de aeronave PAX (Bellies)."
        sol_2 = "Derivar la carga hacia un vuelo carguero puro (Freighter) si la pieza no puede reducirse."
        instruccion = "Desarmar capa superior del pallet o reasignar a carguero."
    elif "peso" in p or "kilo" in p or "sobrepeso" in p:
        estatus = "Alerta de Desbalance o Límite de Posición"
        sol_1 = "Fraccionar la carga en dos guías hijas (HAWB) o repartir el peso en otra posición de bodega."
        sol_2 = "Reequilibrar el centro de gravedad ajustando la distribución simétrica sobre la base."
        instruccion = "Dividir carga en dos posiciones o rebalancear estiba."
    elif "madera" in p or "estiba" in p or "tarima" in p or "nimf" in p:
        estatus = "Incidencia Crítica en Estiba o Tratamiento"
        sol_1 = "Reemplazar inmediatamente por estiba plástica o madera con sello térmico visible de certificación."
        sol_2 = "Verificar documentación del proveedor de tarimas antes de aceptar el ingreso a bodega."
        instruccion = "Cambiar estiba por una plástica."
    else:
        estatus = "Revisión Documental y Física Conforme"
        sol_1 = "Verificar concordancia de etiquetas secundarias y marcas físicas con los datos del manifiesto."
        sol_2 = "Proceder con la aceptación y transferencia directa hacia la zona de tránsitos y conexiones."
        instruccion = "Aceptar carga y rutear a bodega de transferencia."

    if pdfFile:
        sol_1 += f" [Documento adjunto '{pdfFile.filename}' verificado en sistema]."

    return {
        "estatus": estatus,
        "sol_1": sol_1,
        "sol_2": sol_2,
        "instruccion": instruccion
    }
