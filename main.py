import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="SmartCargo SafetyHub",
    description="Servidor Web de producción para SmartCargo SafetyHub",
    version="1.0.0"
)

# Endpoint de comprobación de salud (Health Check & Keep-Alive)
@app.get("/health", status_code=200)
def health_check():
    """
    Endpoint utilizado por Render y servicios de monitoreo para mantener
    la aplicación activa 24/7 sin entrar en estado de suspensión.
    """
    return {"status": "ok", "service": "SmartCargo SafetyHub", "online": True}

# Servir el archivo index.html en la ruta raíz
@app.get("/", response_class=HTMLResponse)
def read_root():
    """
    Entrega la interfaz principal de la aplicación.
    """
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse(content="<h1>Error: index.html no encontrado</h1>", status_code=404)

if __name__ == "__main__":
    import uvicorn
    # Render y otras plataformas asignan dinámicamente un puerto en la variable PORT
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
