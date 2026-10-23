import json
import os
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_FILE = BASE_DIR / "safety_data.json"
DATA_FILE = Path(os.environ.get("SAFETY_DATA_PATH", str(DEFAULT_DATA_FILE)))
TIME_ZONE = os.environ.get("SAFETY_TIME_ZONE", "America/New_York")
ADMIN_ACCESS_CODE = os.environ.get("ADMIN_ACCESS_CODE", "").strip()  # Set a private value in Render; no insecure public default.
LOCK = threading.RLock()
SCHEDULER = BackgroundScheduler(timezone=ZoneInfo(TIME_ZONE))

app = FastAPI(title="SmartCargo SafetyHub", description="Servidor Web de producción para SmartCargo SafetyHub", version="1.1.0")

class LoginPayload(BaseModel):
    code: str = Field(min_length=1, max_length=200)

class AutoModePayload(BaseModel):
    enabled: bool

class AnnouncementPayload(BaseModel):
    targetGroup: str = "ALL"
    priority: str = "Normal"
    validUntil: str = ""
    titleEs: str = ""
    contentEs: str = ""
    titleEn: str = ""
    contentEn: str = ""
    publishTiming: str = "now"
    scheduledAt: str = ""
    recurrence: str = "once"
    authorName: str = Field(min_length=2, max_length=160)
    authorRole: str = Field(min_length=2, max_length=160)
    generalAutoApproved: bool = False


def now_local():
    return datetime.now(ZoneInfo(TIME_ZONE))


def _default_state():
    if DEFAULT_DATA_FILE.exists():
        try:
            return json.loads(DEFAULT_DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"version": 1, "time_zone": TIME_ZONE, "sources": {}, "source_disclaimer": "", "groups": {}, "worker_breathing_exercises": [], "leadership_breathing_exercises": [], "announcements": [], "schedules": [], "settings": {"auto_mode_enabled": False, "auto_publish_general_notices": False}, "audit_log": []}


def load_state():
    if DATA_FILE.exists():
        try:
            loaded = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            defaults = _default_state()
            for key, value in defaults.items():
                loaded.setdefault(key, value)
            return loaded
        except Exception:
            # Preserve a corrupt file for recovery instead of silently overwriting it.
            backup = DATA_FILE.with_suffix(DATA_FILE.suffix + ".corrupt")
            try:
                DATA_FILE.replace(backup)
            except Exception:
                pass
    state = _default_state()
    save_state(state)
    return state


def save_state(state):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp = DATA_FILE.with_suffix(DATA_FILE.suffix + ".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(DATA_FILE)

STATE = load_state()


def require_admin(x_admin_code: str | None):
    if not ADMIN_ACCESS_CODE:
        raise HTTPException(status_code=503, detail="Configura ADMIN_ACCESS_CODE en Render antes de habilitar el Puesto de Mando")
    if not x_admin_code or x_admin_code != ADMIN_ACCESS_CODE:
        raise HTTPException(status_code=401, detail="Autorización de jefatura requerida / Admin authorization required")


def normalize_bilingual(title_es, content_es, title_en, content_en):
    has_es = bool(title_es.strip() and content_es.strip())
    has_en = bool(title_en.strip() and content_en.strip())
    if not has_es and not has_en:
        raise HTTPException(status_code=400, detail="Complete título y mensaje en español o inglés / Enter a title and message in Spanish or English")
    if has_es:
        # Ignore a partially filled second-language panel; one complete language is sufficient.
        if not has_en:
            title_en, content_en = "", ""
    elif has_en:
        title_es, content_es = "", ""
    title = {"es": title_es.strip(), "en": title_en.strip()}
    content = {"es": content_es.strip(), "en": content_en.strip()}
    return title, content


def bullets_from_content(content):
    lines = [part.strip(" \t-•") for part in content.replace("\r", "").replace(".", ".\n").splitlines()]
    lines = [line for line in lines if len(line) > 5]
    return lines[:3] if lines else [content[:240]]


def create_announcement(payload, scheduled=False):
    title, content = normalize_bilingual(payload.titleEs, payload.contentEs, payload.titleEn, payload.contentEn)
    now = now_local()
    valid_until = payload.validUntil or (now.date() + timedelta(days=7)).isoformat()
    try:
        datetime.fromisoformat(valid_until)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha de vigencia inválida / Invalid validity date")
    if payload.priority not in {"Normal", "High"}:
        raise HTTPException(status_code=400, detail="Prioridad inválida / Invalid priority")
    if payload.targetGroup not in {"ALL", "COUNTER", "SCALE", "CARGO", "FORKLIFT", "OFFICE", "SUPERVISION"}:
        raise HTTPException(status_code=400, detail="Grupo destinatario inválido / Invalid target group")
    if payload.priority == "High" and payload.recurrence != "once":
        raise HTTPException(status_code=400, detail="Los avisos urgentes no pueden repetirse automáticamente")
    if payload.recurrence not in {"once", "daily", "weekly", "15days", "30days"}:
        raise HTTPException(status_code=400, detail="Frecuencia inválida / Invalid recurrence")
    if payload.recurrence != "once" and not payload.generalAutoApproved:
        raise HTTPException(status_code=400, detail="Solo se pueden repetir avisos generales expresamente aprobados")
    if payload.recurrence != "once" and payload.targetGroup != "ALL":
        raise HTTPException(status_code=400, detail="La repetición automática solo se permite para avisos generales dirigidos a TODOS")
    if payload.publishTiming not in {"now", "scheduled"}:
        raise HTTPException(status_code=400, detail="Modo de publicación inválido")
    scheduled_at = None
    if payload.publishTiming == "scheduled":
        if not payload.scheduledAt:
            raise HTTPException(status_code=400, detail="Selecciona fecha y hora para programar")
        try:
            scheduled_at = datetime.fromisoformat(payload.scheduledAt)
            if scheduled_at.tzinfo is None:
                scheduled_at = scheduled_at.replace(tzinfo=ZoneInfo(TIME_ZONE))
            scheduled_at = scheduled_at.astimezone(ZoneInfo(TIME_ZONE))
        except ValueError:
            raise HTTPException(status_code=400, detail="Fecha y hora inválidas")
        if scheduled_at <= now:
            raise HTTPException(status_code=400, detail="La fecha programada debe estar en el futuro")
    if payload.recurrence != "once" and not payload.generalAutoApproved:
        raise HTTPException(status_code=400, detail="La repetición automática requiere autorización explícita")
    announcement = {
        "id": "N-" + now.strftime("%Y%m%d-") + uuid.uuid4().hex[:8].upper(),
        "type": {"es": "Aviso urgente" if payload.priority == "High" else "Comunicado general", "en": "Urgent notice" if payload.priority == "High" else "General notice"},
        "priority": payload.priority,
        "title": title,
        "summaryBullets": {lang: bullets_from_content(text) if text else [] for lang, text in content.items()},
        "content": content,
        "author": payload.authorName.strip(),
        "authorRole": payload.authorRole.strip(),
        "targetGroup": payload.targetGroup,
        "status": "Scheduled" if scheduled_at else "Active",
        "createdAt": now.isoformat(),
        "validUntil": valid_until,
        "scheduledAt": scheduled_at.isoformat() if scheduled_at else None,
        "recurrence": payload.recurrence,
        "generalAutoApproved": bool(payload.generalAutoApproved),
        "publishSource": "scheduled" if scheduled_at else "manual"
    }
    with LOCK:
        STATE.setdefault("announcements", []).insert(0, announcement)
        if scheduled_at:
            STATE.setdefault("schedules", []).append({"announcementId": announcement["id"], "nextRunAt": scheduled_at.isoformat(), "recurrence": payload.recurrence, "enabled": True, "lastSentAt": None})
            STATE.setdefault("audit_log", []).append({"action": "scheduled", "id": announcement["id"], "author": announcement["author"], "at": now.isoformat()})
        else:
            if payload.recurrence in {"daily", "weekly", "15days", "30days"}:
                step = {"daily": timedelta(days=1), "weekly": timedelta(days=7), "15days": timedelta(days=15), "30days": timedelta(days=30)}[payload.recurrence]
                STATE.setdefault("schedules", []).append({"announcementId": announcement["id"], "nextRunAt": (now + step).isoformat(), "recurrence": payload.recurrence, "enabled": True, "lastSentAt": now.isoformat()})
            STATE.setdefault("audit_log", []).append({"action": "published", "id": announcement["id"], "author": announcement["author"], "at": now.isoformat()})
        save_state(STATE)
    return announcement


def process_schedules():
    """Publishes due approved messages. Runs inside the Render web-service process."""
    now = now_local()
    with LOCK:
        changed = False
        for item in STATE.get("announcements", []):
            if item.get("status") == "Active" and item.get("validUntil"):
                try:
                    if datetime.fromisoformat(item["validUntil"]).date() < now.date():
                        item["status"] = "Withdrawn"
                        changed = True
                except ValueError:
                    pass
        for schedule in STATE.get("schedules", []):
            if not schedule.get("enabled"):
                continue
            try:
                due = datetime.fromisoformat(schedule["nextRunAt"])
                if due.tzinfo is None:
                    due = due.replace(tzinfo=ZoneInfo(TIME_ZONE))
                due = due.astimezone(ZoneInfo(TIME_ZONE))
            except (ValueError, TypeError):
                schedule["enabled"] = False
                changed = True
                continue
            if due > now:
                continue
            if schedule.get("recurrence") in {"daily", "weekly", "15days", "30days"} and not STATE.get("settings", {}).get("auto_mode_enabled", False):
                continue
            original = next((a for a in STATE.get("announcements", []) if a.get("id") == schedule.get("announcementId")), None)
            if not original:
                schedule["enabled"] = False
                changed = True
                continue
            if original.get("validUntil"):
                try:
                    if datetime.fromisoformat(original["validUntil"]).date() < now.date():
                        original["status"] = "Withdrawn"
                        schedule["enabled"] = False
                        changed = True
                        continue
                except ValueError:
                    pass
            # A future one-time message remains in schedules until due; recurring messages clone the approved general notice.
            if original.get("status") == "Scheduled":
                original["status"] = "Active"
                original["createdAt"] = now.isoformat()
                original["scheduledAt"] = None
                STATE.setdefault("audit_log", []).append({"action": "scheduled_published", "id": original["id"], "at": now.isoformat()})
            elif schedule.get("recurrence") in {"daily", "weekly", "15days", "30days"} and original.get("generalAutoApproved") and original.get("priority") != "High":
                clone = deepcopy(original)
                clone["id"] = "N-" + now.strftime("%Y%m%d-") + uuid.uuid4().hex[:8].upper()
                clone["createdAt"] = now.isoformat()
                clone["status"] = "Active"
                clone["publishSource"] = "automatic"
                STATE.setdefault("announcements", []).insert(0, clone)
                STATE.setdefault("audit_log", []).append({"action": "automatic_published", "id": clone["id"], "at": now.isoformat()})
            recurrence = schedule.get("recurrence", "once")
            if recurrence == "once":
                schedule["enabled"] = False
            else:
                step = {"daily": timedelta(days=1), "weekly": timedelta(days=7), "15days": timedelta(days=15), "30days": timedelta(days=30)}[recurrence]
                next_due = due + step
                while next_due <= now:
                    next_due += step
                schedule["nextRunAt"] = next_due.isoformat()
                schedule["lastSentAt"] = now.isoformat()
            changed = True
        if changed:
            save_state(STATE)


def daily_reminders_for(group_id, today):
    bank = STATE.get("groups", {}).get(group_id, [])
    if not bank:
        return []
    # Deterministic server-side rotation: all devices see the same 3 for the same station/date.
    seed = sum(ord(ch) for ch in f"{today}:{group_id}")
    start = seed % len(bank)
    step = max(1, len(bank) // 3)
    indexes = []
    for offset in range(len(bank)):
        idx = (start + offset * step) % len(bank)
        if idx not in indexes:
            indexes.append(idx)
        if len(indexes) == 3:
            break
    return [bank[i] for i in indexes]

@app.on_event("startup")
def startup_event():
    if not SCHEDULER.running:
        SCHEDULER.add_job(process_schedules, "interval", seconds=20, id="smartcargo_schedules", replace_existing=True, max_instances=1, coalesce=True)
        SCHEDULER.start()

@app.on_event("shutdown")
def shutdown_event():
    if SCHEDULER.running:
        SCHEDULER.shutdown(wait=False)

@app.get("/health", status_code=200)
def health_check():
    return {"status": "ok", "service": "SmartCargo SafetyHub", "online": True, "scheduler": SCHEDULER.running, "data_file": str(DATA_FILE)}

@app.get("/", response_class=HTMLResponse)
def read_root():
    html_path = BASE_DIR / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>Error: index.html no encontrado</h1>", status_code=404)

@app.post("/api/admin/login")
def admin_login(payload: LoginPayload):
    if not ADMIN_ACCESS_CODE:
        raise HTTPException(status_code=503, detail="Configura ADMIN_ACCESS_CODE en Render antes de habilitar el Puesto de Mando")
    if payload.code != ADMIN_ACCESS_CODE:
        raise HTTPException(status_code=401, detail="Clave incorrecta / Invalid access code")
    return {"ok": True}

@app.get("/api/bootstrap")
def bootstrap(group: str = "COUNTER"):
    if group not in STATE.get("groups", {}):
        group = "COUNTER"
    today = now_local().date().isoformat()
    with LOCK:
        notices = [deepcopy(a) for a in STATE.get("announcements", []) if a.get("status") == "Active" and (a.get("targetGroup") in {"ALL", group}) and (not a.get("validUntil") or a.get("validUntil") >= today)]
        settings = deepcopy(STATE.get("settings", {}))
    return {"today": today, "daily_reminders": daily_reminders_for(group, today), "announcements": notices, "settings": settings, "time_zone": TIME_ZONE, "source_disclaimer": STATE.get("source_disclaimer", "")}

@app.get("/api/reminder-bank")
def reminder_bank():
    return {"groups": STATE.get("groups", {}), "sources": STATE.get("sources", {}), "total": sum(len(v) for v in STATE.get("groups", {}).values())}

@app.get("/api/breathing-exercises")
def breathing_exercises():
    return {"worker": STATE.get("worker_breathing_exercises", []), "leadership": STATE.get("leadership_breathing_exercises", [])}

@app.post("/api/admin/auto-mode")
def set_auto_mode(payload: AutoModePayload, x_admin_code: str | None = Header(default=None)):
    require_admin(x_admin_code)
    with LOCK:
        STATE.setdefault("settings", {})["auto_mode_enabled"] = payload.enabled
        save_state(STATE)
    return {"enabled": payload.enabled}

@app.post("/api/admin/announcements")
def publish_announcement(payload: AnnouncementPayload, x_admin_code: str | None = Header(default=None)):
    require_admin(x_admin_code)
    if payload.publishTiming == "scheduled":
        announcement = create_announcement(payload, scheduled=True)
        return {"ok": True, "id": announcement["id"], "message": "Aviso programado / Notice scheduled", "status": "Scheduled"}
    announcement = create_announcement(payload, scheduled=False)
    return {"ok": True, "id": announcement["id"], "message": "Contenido publicado / Content published", "status": "Active"}

@app.post("/api/admin/announcements/{notice_id}/withdraw")
def withdraw_announcement(notice_id: str, request: Request, x_admin_code: str | None = Header(default=None)):
    require_admin(x_admin_code)
    with LOCK:
        found = False
        for item in STATE.get("announcements", []):
            if item.get("id") == notice_id:
                item["status"] = "Withdrawn"
                found = True
                STATE.setdefault("audit_log", []).append({"action": "withdrawn", "id": notice_id, "at": now_local().isoformat()})
        for schedule in STATE.get("schedules", []):
            if schedule.get("announcementId") == notice_id:
                schedule["enabled"] = False
        save_state(STATE)
    if not found:
        raise HTTPException(status_code=404, detail="Aviso no encontrado / Notice not found")
    return {"ok": True}

@app.get("/api/admin/status")
def admin_status(x_admin_code: str | None = Header(default=None)):
    require_admin(x_admin_code)
    with LOCK:
        return {"settings": STATE.get("settings", {}), "schedules": STATE.get("schedules", []), "audit_log": STATE.get("audit_log", [])[-100:], "announcements": STATE.get("announcements", [])}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
