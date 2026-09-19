const form = document.getElementById("smartcargoForm");
const photosInput = document.getElementById("photos");
const photosList = document.getElementById("photosList");

const resultado = document.getElementById("resultado");
const resultadoEstado = document.getElementById("resultadoEstado");
const resultadoResumen = document.getElementById("resultadoResumen");
const problemas = document.getElementById("problemas");
const reglaOro = document.getElementById("reglaOro");

const loading = document.getElementById("loading");

let fotosSeleccionadas = [];


function esc(texto) {
    const div = document.createElement("div");
    div.textContent = texto ?? "";
    return div.innerHTML;
}


function mostrarFotosSeleccionadas() {
    if (!photosList) return;

    photosList.innerHTML = "";

    if (!fotosSeleccionadas.length) {
        photosList.textContent =
            "Ninguna fotografía seleccionada.";
        return;
    }

    const titulo = document.createElement("div");

    titulo.className = "photos-count";

    titulo.textContent =
        `${fotosSeleccionadas.length} fotografía(s) seleccionada(s)`;

    photosList.appendChild(titulo);

    const gallery = document.createElement("div");

    gallery.className = "photo-gallery";

    fotosSeleccionadas.forEach((file, index) => {
        const item = document.createElement("div");

        item.className = "photo-item";

        const img = document.createElement("img");

        img.src = URL.createObjectURL(file);

        img.alt =
            `Mercancía - fotografía ${index + 1}`;

        img.onload = () => {
            URL.revokeObjectURL(img.src);
        };

        const label = document.createElement("div");

        label.className = "photo-label";

        label.textContent =
            `Foto ${index + 1}`;

        item.appendChild(img);
        item.appendChild(label);

        gallery.appendChild(item);
    });

    photosList.appendChild(gallery);
}


if (photosInput) {
    photosInput.addEventListener(
        "change",
        () => {
            fotosSeleccionadas =
                Array.from(
                    photosInput.files || []
                );

            mostrarFotosSeleccionadas();
        }
    );
}


function mostrarEvidenciaVisual(fotos) {
    if (!fotos || !fotos.length) {
        return "";
    }

    let html = `
        <section class="evidence-section">
            <div class="evidence-title">
                EVIDENCIA VISUAL DE LA MERCANCÍA
            </div>

            <div class="evidence-note">
                Fotografías presentadas por el usuario como
                evidencia visual de la mercancía.
                La fotografía no sustituye la inspección física
                ni la aceptación oficial.
            </div>

            <div class="photo-gallery result-gallery">
    `;

    fotos.forEach((foto, index) => {
        html += `
            <div class="photo-item">
                <img
                    src="${foto.data}"
                    alt="Mercancía - fotografía ${index + 1}"
                >
                <div class="photo-label">
                    Foto ${index + 1}
                    ${foto.nombre
                        ? ` · ${esc(foto.nombre)}`
                        : ""}
                </div>
            </div>
        `;
    });

    html += `
            </div>
        </section>
    `;

    return html;
}


function mostrarProblemas(lista) {
    if (!problemas) return;

    problemas.innerHTML = "";

    if (!lista || !lista.length) {
        problemas.innerHTML = `
            <div class="problem-empty">
                No se detectaron problemas básicos.
            </div>
        `;

        return;
    }

    lista.forEach((problema) => {
        const item = document.createElement("div");

        item.className =
            `problem problem-${String(
                problema.estado || ""
            ).toLowerCase()}`;

        item.innerHTML = `
            <div class="problem-state">
                ${esc(problema.estado)}
            </div>

            <div class="problem-message">
                ${esc(problema.mensaje)}
            </div>

            ${
                problema.accion
                    ? `
                    <div class="problem-action">
                        <strong>Acción:</strong>
                        ${esc(problema.accion)}
                    </div>
                    `
                    : ""
            }

            ${
                problema.codigo
                    ? `
                    <div class="problem-code">
                        ${esc(problema.codigo)}
                    </div>
                    `
                    : ""
            }
        `;

        problemas.appendChild(item);
    });
}


function mostrarResultado(data) {
    if (!resultado) return;

    resultado.style.display = "block";

    if (resultadoEstado) {
        resultadoEstado.textContent =
            data.estado || "REVISAR";

        resultadoEstado.className =
            `resultado-estado resultado-${String(
                data.estado || ""
            ).toLowerCase()}`;
    }

    if (resultadoResumen) {
        resultadoResumen.textContent =
            data.resumen || "";
    }

    mostrarProblemas(
        data.problemas || []
    );

    if (reglaOro) {
        reglaOro.textContent =
            data.regla_de_oro || "";
    }

    const antiguaEvidencia =
        document.getElementById(
            "evidenciaVisualResultado"
        );

    if (antiguaEvidencia) {
        antiguaEvidencia.remove();
    }

    const evidenciaHTML =
        mostrarEvidenciaVisual(
            data.evidencia_visual || []
        );

    if (evidenciaHTML) {
        const bloque =
            document.createElement("div");

        bloque.id =
            "evidenciaVisualResultado";

        bloque.innerHTML =
            evidenciaHTML;

        resultado.appendChild(bloque);
    }

    resultado.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


if (form) {
    form.addEventListener(
        "submit",
        async (event) => {
            event.preventDefault();

            if (loading) {
                loading.style.display = "block";
            }

            if (resultado) {
                resultado.style.display = "none";
            }

            try {
                const formData =
                    new FormData(form);

                formData.delete("photos");

                fotosSeleccionadas.forEach(
                    (foto) => {
                        formData.append(
                            "photos",
                            foto,
                            foto.name
                        );
                    }
                );

                const response =
                    await fetch(
                        "/api/smartcargo/resolver",
                        {
                            method: "POST",
                            body: formData
                        }
                    );

                const data =
                    await response.json();

                if (!response.ok) {
                    throw new Error(
                        data.detail ||
                        "No fue posible procesar la solicitud."
                    );
                }

                mostrarResultado(data);

            } catch (error) {
                if (resultado) {
                    resultado.style.display =
                        "block";
                }

                if (resultadoEstado) {
                    resultadoEstado.textContent =
                        "ERROR";

                    resultadoEstado.className =
                        "resultado-estado resultado-corregir";
                }

                if (resultadoResumen) {
                    resultadoResumen.textContent =
                        error.message ||
                        "Ocurrió un error al procesar la carga.";
                }

                if (problemas) {
                    problemas.innerHTML = "";
                }

            } finally {
                if (loading) {
                    loading.style.display = "none";
                }
            }
        }
    );
}


mostrarFotosSeleccionadas();
