let rolActual = "";

const ROLES = {
    camionero: {
        nombre: "Camionero",
        descripcion:
            "Comprueba que tu carga esté preparada antes de llevarla a presentar."
    },

    dueno: {
        nombre: "Dueño de la mercancía",
        descripcion:
            "Revisa tu mercancía y tus documentos antes de continuar."
    },

    forwarder: {
        nombre: "Forwarder",
        descripcion:
            "Revisa el expediente y busca diferencias entre documentos y datos."
    },

    counter: {
        nombre: "Agente de Counter",
        descripcion:
            "Realiza una revisión completa de documentos, carga y datos."
    }
};


/* =========================================================
   INICIO
========================================================= */

document.addEventListener("DOMContentLoaded", () => {

    const formulario = document.getElementById("formulario");

    if (formulario) {
        formulario.addEventListener("submit", event => {
            event.preventDefault();
            revisarCarga();
        });
    }

});


/* =========================================================
   SELECCIONAR ROL
========================================================= */

function seleccionarRol(rol) {

    if (!ROLES[rol]) {
        mostrarError("No se reconoce el rol seleccionado.");
        return;
    }

    rolActual = rol;

    const inicio = document.getElementById("inicio");
    const formulario = document.getElementById("formulario");
    const resultado = document.getElementById("resultado");

    inicio?.classList.add("hidden");
    resultado?.classList.add("hidden");
    formulario?.classList.remove("hidden");

    const info = ROLES[rol];

    const rolTexto = document.getElementById("rolTexto");
    const titulo = document.getElementById("tituloRol");
    const descripcion = document.getElementById("descripcionRol");

    if (rolTexto) {
        rolTexto.textContent = info.nombre;
    }

    if (titulo) {
        titulo.textContent = info.nombre;
    }

    if (descripcion) {
        descripcion.textContent = info.descripcion;
    }

    const avanzados =
        document.getElementById("datosAvanzados");

    if (avanzados) {

        if (rol === "forwarder" || rol === "counter") {
            avanzados.classList.remove("hidden");
        } else {
            avanzados.classList.add("hidden");
        }
    }

    arriba();
}


/* =========================================================
   VOLVER AL INICIO
========================================================= */

function volverInicio() {

    document.getElementById("formulario")
        ?.classList.add("hidden");

    document.getElementById("resultado")
        ?.classList.add("hidden");

    document.getElementById("inicio")
        ?.classList.remove("hidden");

    arriba();
}


/* =========================================================
   VOLVER AL FORMULARIO
========================================================= */

function volverFormulario() {

    document.getElementById("resultado")
        ?.classList.add("hidden");

    document.getElementById("formulario")
        ?.classList.remove("hidden");

    arriba();
}


/* =========================================================
   NUEVA REVISION
========================================================= */

function nuevoProceso() {

    rolActual = "";

    const formulario =
        document.getElementById("formulario");

    if (formulario) {

        formulario
            .querySelectorAll("input, textarea")
            .forEach(elemento => {

                if (elemento.type !== "file") {
                    elemento.value = "";
                }
            });

        formulario
            .querySelectorAll("input[type=file]")
            .forEach(elemento => {
                elemento.value = "";
            });
    }

    const tipo =
        document.getElementById("tipo_carga");

    if (tipo) {
        tipo.value = "general";
    }

    const embalaje =
        document.getElementById("embalaje");

    if (embalaje) {
        embalaje.value = "";
    }

    volverInicio();
}


/* =========================================================
   OBTENER VALOR
========================================================= */

function valor(id) {

    const elemento =
        document.getElementById(id);

    return elemento
        ? elemento.value.trim()
        : "";
}


/* =========================================================
   CREAR FORM DATA
========================================================= */

function crearFormulario() {

    const datos = new FormData();

    datos.append("rol", rolActual);

    datos.append(
        "tipo_carga",
        valor("tipo_carga") || "general"
    );

    datos.append(
        "descripcion",
        valor("descripcion")
    );

    datos.append(
        "piezas",
        valor("piezas") || "0"
    );

    datos.append(
        "peso",
        valor("peso") || "0"
    );

    datos.append(
        "largo",
        valor("largo") || "0"
    );

    datos.append(
        "ancho",
        valor("ancho") || "0"
    );

    datos.append(
        "alto",
        valor("alto") || "0"
    );

    datos.append(
        "embalaje",
        valor("embalaje")
    );

    datos.append(
        "shipper",
        valor("shipper")
    );

    datos.append(
        "consignee",
        valor("consignee")
    );

    datos.append(
        "origen",
        valor("origen")
    );

    datos.append(
        "destino",
        valor("destino")
    );

    datos.append(
        "awb",
        valor("awb")
    );


    /* =========================
       DOCUMENTOS
    ========================= */

    const documentos =
        document.getElementById("documentos");

    if (documentos?.files) {

        for (const archivo of documentos.files) {

            datos.append(
                "documentos",
                archivo,
                archivo.name
            );
        }
    }


    /* =========================
       FOTOS
    ========================= */

    const fotos =
        document.getElementById("fotos");

    if (fotos?.files) {

        for (const archivo of fotos.files) {

            datos.append(
                "fotos",
                archivo,
                archivo.name
            );
        }
    }

    return datos;
}


/* =========================================================
   REVISAR CARGA
========================================================= */

async function revisarCarga() {

    if (!rolActual) {
        mostrarError(
            "Primero selecciona tu rol."
        );
        return;
    }

    const boton =
        document.getElementById("btnRevisar");

    if (boton) {

        boton.disabled = true;

        boton.innerHTML = `
            <span class="loading">
                <span class="spinner"></span>
                Revisando...
            </span>
        `;
    }

    try {

        const datos =
            crearFormulario();

        const respuesta =
            await fetch(
                "/api/smartcargo/resolver",
                {
                    method: "POST",
                    body: datos
                }
            );

        let resultado;

        try {

            resultado =
                await respuesta.json();

        } catch {

            throw new Error(
                "El servidor no devolvió una respuesta válida."
            );
        }

        if (!respuesta.ok) {

            throw new Error(
                resultado.detail ||
                resultado.message ||
                "No se pudo realizar la revisión."
            );
        }

        mostrarResultado(resultado);

    } catch (error) {

        mostrarError(
            error?.message ||
            "Ocurrió un error durante la revisión."
        );

    } finally {

        if (boton) {

            boton.disabled = false;
            boton.textContent =
                "Revisar mi carga";
        }
    }
}


/* =========================================================
   MOSTRAR RESULTADO
========================================================= */

function mostrarResultado(data) {

    document.getElementById("formulario")
        ?.classList.add("hidden");

    document.getElementById("resultado")
        ?.classList.remove("hidden");

    const caja =
        document.getElementById("resultadoCaja");

    const lista =
        document.getElementById("problemas");

    if (!caja || !lista) {
        return;
    }

    lista.innerHTML = "";

    const estado =
        String(data.estado || "").toUpperCase();


    /* =========================
       LISTO
    ========================= */

    if (estado === "LISTO") {

        caja.className =
            "result ready";

        caja.innerHTML = `
            <h2>✅ LISTO</h2>

            <p>
                ${escapeHTML(
                    data.resumen ||
                    "No se detectaron problemas pendientes."
                )}
            </p>

            <p class="mini">
                Esta es una revisión previa de la
                información proporcionada.
            </p>
        `;
    }


    /* =========================
       REVISAR
    ========================= */

    else if (estado === "REVISAR") {

        caja.className =
            "result review-box";

        caja.innerHTML = `
            <h2>⚠️ REVISAR</h2>

            <p>
                ${escapeHTML(
                    data.resumen ||
                    "Hay información que debe revisarse."
                )}
            </p>

            <p>
                No continúes hasta revisar los puntos indicados.
            </p>
        `;
    }


    /* =========================
       CORREGIR
    ========================= */

    else {

        caja.className =
            "result correct";

        caja.innerHTML = `
            <h2>❌ CORREGIR</h2>

            <p>
                ${escapeHTML(
                    data.resumen ||
                    "Hay información que debe corregirse."
                )}
            </p>

            <p>
                Corrige los problemas indicados
                y vuelve a revisar.
            </p>
        `;
    }


    /* =========================
       PROBLEMAS
    ========================= */

    const problemas =
        Array.isArray(data.problemas)
            ? data.problemas
            : [];

    if (!problemas.length) {

        lista.innerHTML = `
            <div class="check">
                No se detectaron problemas pendientes.
            </div>
        `;

    } else {

        problemas.forEach(problema => {

            const div =
                document.createElement("div");

            div.className =
                "problem" +
                (
                    problema.estado === "REVISAR"
                        ? " review"
                        : ""
                );

            const mensaje =
                problema.mensaje ||
                "Problema detectado.";

            const accion =
                problema.accion ||
                "";

            const codigo =
                problema.codigo ||
                "";

            div.innerHTML = `
                <strong>
                    ${escapeHTML(mensaje)}
                </strong>

                ${
                    accion
                    ? `<div>${escapeHTML(accion)}</div>`
                    : ""
                }

                ${
                    codigo
                    ? `<div class="mini">
                        Referencia: ${escapeHTML(codigo)}
                       </div>`
                    : ""
                }
            `;

            lista.appendChild(div);
        });
    }

    arriba();
}


/* =========================================================
   ERROR DE COMUNICACION
========================================================= */

function mostrarError(mensaje) {

    document.getElementById("formulario")
        ?.classList.add("hidden");

    document.getElementById("resultado")
        ?.classList.remove("hidden");

    const caja =
        document.getElementById("resultadoCaja");

    const lista =
        document.getElementById("problemas");

    if (caja) {

        caja.className =
            "result correct";

        caja.innerHTML = `
            <h2>❌ No se pudo completar la revisión</h2>

            <p>
                ${escapeHTML(mensaje)}
            </p>

            <p>
                Revisa la información e inténtalo nuevamente.
            </p>
        `;
    }

    if (lista) {
        lista.innerHTML = "";
    }

    arriba();
}


/* =========================================================
   SEGURIDAD HTML
========================================================= */

function escapeHTML(valor) {

    return String(valor)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}


/* =========================================================
   ARRIBA
========================================================= */

function arriba() {

    window.scrollTo({
        top: 0,
        behavior: "smooth"
    });
}
