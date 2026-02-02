"""
Single-file Dining Reservation Chatbot Website (FastAPI)

What you get (all-in-one):
- Website UI (served at /) with:
  - Simple inputs (Guests, Date, Time, Name, Phone, Reservation ID)
  - Buttons: Check availability / Book / Modify / Cancel / Menu
  - Chat panel (optional text)
- Backend API (served at /chat) with:
  - Structured availability schedules (no fabricated availability)
  - Fast cached slot lookups
  - Reservation create/modify/cancel
  - Compressed menu data (short names; expands only on request)

Run:
  pip install fastapi uvicorn pydantic
  python app.py
Then open:
  http://127.0.0.1:8000

Production note:
- Storage is in-memory for speed/demo. Replace with DB for persistence.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, time, date
from typing import Dict, List, Optional, Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn


# -----------------------------
# Compressed Menu Data
# -----------------------------
MENU = {
    "Starters": [("Soup", "Tomato basil soup"), ("Fries", "Classic fries"), ("Bruschetta", "Tomato, basil, toasted bread")],
    "Mains": [("Pasta", "Penne in alfredo or arrabbiata"), ("Pizza", "Margherita / Veg Supreme"), ("Bowl", "Grain bowl with seasonal veg")],
    "Dessert": [("Brownie", "Warm brownie, ice cream"), ("Cheesecake", "Classic baked cheesecake")],
    "Drinks": [("Coffee", "Espresso / Americano"), ("Tea", "Assorted teas"), ("Soda", "Soft drinks")],
}


# -----------------------------
# Models
# -----------------------------
@dataclass
class Reservation:
    reservation_id: str
    name: str
    phone: Optional[str]
    party_size: int
    reservation_date: date
    reservation_time: time
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def dt(self) -> datetime:
        return datetime.combine(self.reservation_date, self.reservation_time)


@dataclass
class SlotSchedule:
    open_time: time
    close_time: time
    slot_minutes: int = 30
    turn_minutes: int = 90

    def slots_for_date(self, d: date) -> List[time]:
        start_dt = datetime.combine(d, self.open_time)
        end_latest_start = datetime.combine(d, self.close_time) - timedelta(minutes=self.turn_minutes)
        slots: List[time] = []
        cur = start_dt
        while cur <= end_latest_start:
            slots.append(cur.time().replace(second=0, microsecond=0))
            cur += timedelta(minutes=self.slot_minutes)
        return slots


@dataclass
class RestaurantConfig:
    name: str = "Dining Reservation Chatbot"
    total_seats: int = 40
    schedule: SlotSchedule = field(default_factory=lambda: SlotSchedule(open_time=time(12, 0), close_time=time(23, 0)))


@dataclass
class SessionState:
    name: Optional[str] = None
    phone: Optional[str] = None
    last_reservation_id: Optional[str] = None


# -----------------------------
# Engine (fast + no fabricated availability)
# -----------------------------
class ReservationEngine:
    def __init__(self, config: RestaurantConfig):
        self.config = config
        self.reservations: Dict[str, Reservation] = {}
        self._cache: Dict[date, Dict[time, int]] = {}

    def _invalidate(self, d: date) -> None:
        self._cache.pop(d, None)

    def _occupied_slots(self, r: Reservation) -> List[time]:
        sched = self.config.schedule
        start_dt = r.dt
        end_dt = start_dt + timedelta(minutes=sched.turn_minutes)
        slots = []
        cur = start_dt
        while cur < end_dt:
            slots.append(cur.time().replace(second=0, microsecond=0))
            cur += timedelta(minutes=sched.slot_minutes)
        return slots

    def _build_cache(self, d: date) -> None:
        used = {s: 0 for s in self.config.schedule.slots_for_date(d)}
        for r in self.reservations.values():
            if r.reservation_date != d:
                continue
            for s in self._occupied_slots(r):
                if s in used:
                    used[s] += r.party_size
        self._cache[d] = used

    def _can_fit(self, d: date, start_t: time, party_size: int, ignore_id: Optional[str] = None) -> bool:
        slots_set = set(self.config.schedule.slots_for_date(d))
        if start_t not in slots_set:
            return False

        if d not in self._cache:
            self._build_cache(d)

        used = dict(self._cache[d])

        if ignore_id and ignore_id in self.reservations:
            old = self.reservations[ignore_id]
            if old.reservation_date == d:
                for s in self._occupied_slots(old):
                    if s in used:
                        used[s] -= old.party_size

        sched = self.config.schedule
        start_dt = datetime.combine(d, start_t)
        end_dt = start_dt + timedelta(minutes=sched.turn_minutes)

        cur = start_dt
        while cur < end_dt:
            s = cur.time().replace(second=0, microsecond=0)
            if s not in slots_set:
                return False
            if used.get(s, 0) + party_size > self.config.total_seats:
                return False
            cur += timedelta(minutes=sched.slot_minutes)

        return True

    def availability(self, d: date, party_size: int) -> List[time]:
        slots = self.config.schedule.slots_for_date(d)
        return [s for s in slots if self._can_fit(d, s, party_size)]

    def create(self, name: str, phone: Optional[str], party_size: int, d: date, t: time) -> Reservation:
        if not self._can_fit(d, t, party_size):
            raise ValueError("Slot unavailable.")
        rid = "R-" + uuid.uuid4().hex[:10].upper()
        r = Reservation(rid, name, phone, party_size, d, t)
        self.reservations[rid] = r
        self._invalidate(d)
        return r

    def modify(self, rid: str, *, party_size: Optional[int] = None, d: Optional[date] = None, t: Optional[time] = None) -> Reservation:
        if rid not in self.reservations:
            raise KeyError("Not found.")
        r = self.reservations[rid]
        new_party = party_size if party_size is not None else r.party_size
        new_d = d if d is not None else r.reservation_date
        new_t = t if t is not None else r.reservation_time

        if not self._can_fit(new_d, new_t, new_party, ignore_id=rid):
            raise ValueError("Slot unavailable.")

        old_d = r.reservation_date
        r.party_size = new_party
        r.reservation_date = new_d
        r.reservation_time = new_t
        self._invalidate(old_d)
        self._invalidate(new_d)
        return r

    def cancel(self, rid: str) -> Reservation:
        if rid not in self.reservations:
            raise KeyError("Not found.")
        r = self.reservations.pop(rid)
        self._invalidate(r.reservation_date)
        return r

    def get(self, rid: str) -> Optional[Reservation]:
        return self.reservations.get(rid)


# -----------------------------
# Helpers
# -----------------------------
def fmt_time(t: time) -> str:
    h = t.hour
    suffix = "AM" if h < 12 else "PM"
    hh = h % 12
    if hh == 0:
        hh = 12
    return f"{hh}:{t.minute:02d} {suffix}"


def parse_date_iso(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return date.fromisoformat(s)


def parse_time_hhmm(s: Optional[str]) -> Optional[time]:
    if not s:
        return None
    hh, mm = s.split(":")
    return time(int(hh), int(mm))


def menu_response(details: bool) -> str:
    lines = ["Menu"]
    for cat, items in MENU.items():
        if details:
            lines.append(f"\n{cat}:")
            for n, desc in items:
                lines.append(f"- {n}: {desc}")
        else:
            lines.append(f"\n{cat}: " + ", ".join(n for n, _ in items))
    return "\n".join(lines)


def reservation_summary(r: Reservation, heading: str = "Reservation confirmed.") -> str:
    return (
        f"{heading}\n"
        f"- Reference: {r.reservation_id}\n"
        f"- Name: {r.name}\n"
        f"- Guests: {r.party_size}\n"
        f"- Date: {r.reservation_date.isoformat()}\n"
        f"- Time: {fmt_time(r.reservation_time)}"
    )


def serialize_reservation(r: Reservation) -> Dict[str, Any]:
    return {
        "reservation_id": r.reservation_id,
        "name": r.name,
        "phone": r.phone,
        "guests": r.party_size,
        "date": r.reservation_date.isoformat(),
        "time": fmt_time(r.reservation_time),
    }


# -----------------------------
# App
# -----------------------------
app = FastAPI(title="Dining Reservation Chatbot (Single File)", version="1.0")
engine = ReservationEngine(RestaurantConfig())
sessions: Dict[str, SessionState] = {}


class ChatRequest(BaseModel):
    session_id: str

    # Free text message (optional). UI uses it mainly for chat-style interaction.
    message: str = ""

    # UI-first structured fields (recommended)
    action: Optional[str] = None  # availability | book | modify | cancel | menu
    date: Optional[str] = None    # YYYY-MM-DD
    time: Optional[str] = None    # HH:MM (24h)
    guests: Optional[int] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    reservation_id: Optional[str] = None
    menu_details: Optional[bool] = False


class ChatResponse(BaseModel):
    reply: str
    available_times: Optional[List[str]] = None
    active_reservation: Optional[Dict[str, Any]] = None


def get_session(sid: str) -> SessionState:
    if sid not in sessions:
        sessions[sid] = SessionState()
    return sessions[sid]


INDEX_HTML = """<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Dining Reservation Chatbot</title>
  <style>
    :root { font-family: system-ui, -apple-system, Segoe UI, Roboto, Arial; }
    body { margin: 0; background:#0b1220; color:#e8eefc; }
    .wrap { max-width: 1100px; margin: 0 auto; padding: 20px; }
    .grid { display: grid; grid-template-columns: 380px 1fr; gap: 16px; }
    .card { background:#121b30; border:1px solid #223055; border-radius:14px; padding:14px; }
    h1 { margin: 0 0 12px 0; font-size: 18px; }
    .small { font-size: 12px; color:#b9c7ef; }
    label { display:block; font-size:12px; color:#b9c7ef; margin:10px 0 6px; }
    input, select, button, textarea {
      width: 100%; box-sizing: border-box; padding: 10px;
      border-radius: 10px; border: 1px solid #2a3b66;
      background:#0e1730; color:#e8eefc;
    }
    button { cursor:pointer; border:1px solid #35508d; background:#16305f; }
    button:hover { background:#1c3b76; }
    .row { display:flex; gap:10px; }
    .row > * { flex:1; }
    .actions { display:grid; grid-template-columns: 1fr 1fr; gap:10px; margin-top:12px; }
    .chatbox { height: 520px; overflow:auto; padding: 10px; background:#0e1730; border-radius:12px; border:1px solid #2a3b66; }
    .msg { margin: 10px 0; line-height: 1.35; white-space: pre-wrap; }
    .me { color:#b7ffdf; }
    .bot { color:#e8eefc; }
    .pill { display:inline-block; padding: 6px 10px; border-radius: 999px; border:1px solid #2a3b66; margin-right:8px; font-size:12px; }
    textarea { resize:none; height: 70px; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Dining Reservation Chatbot</h1>
    <div class="small">Fast availability, bookings, modifications, cancellations, and menu. Prefer the controls; chat is optional.</div>
    <div class="grid" style="margin-top:14px;">
      <div class="card">
        <div class="small">
          <span class="pill">Simple Inputs</span>
          <span class="pill">No Guessing</span>
          <span class="pill">Slot Schedules</span>
        </div>

        <label>Session ID (keep as-is)</label>
        <input id="session_id" value="web-session" />

        <div class="row">
          <div>
            <label>Guests</label>
            <select id="guests"></select>
          </div>
          <div>
            <label>Date</label>
            <input id="date" type="date" />
          </div>
        </div>

        <label>Time (populate via availability)</label>
        <select id="time"></select>

        <div class="row">
          <div>
            <label>Name</label>
            <input id="name" placeholder="Enter name" />
          </div>
          <div>
            <label>Phone (optional)</label>
            <input id="phone" placeholder="Enter phone" />
          </div>
        </div>

        <label>Reservation Reference (for modify/cancel)</label>
        <input id="reservation_id" placeholder="R-XXXXXXXXXX" />

        <div class="actions">
          <button onclick="checkAvailability()">Check availability</button>
          <button onclick="book()">Book</button>
          <button onclick="modify()">Modify</button>
          <button onclick="cancelRes()">Cancel</button>
          <button onclick="menu(false)">Menu (short)</button>
          <button onclick="menu(true)">Menu (details)</button>
        </div>

        <label style="margin-top:14px;">Optional chat message</label>
        <textarea id="message" placeholder="Ask: menu, availability, book, modify, cancel"></textarea>
        <button style="margin-top:10px;" onclick="sendChat()">Send chat</button>
      </div>

      <div class="card">
        <div class="small">Conversation</div>
        <div id="chatbox" class="chatbox"></div>
      </div>
    </div>
  </div>

<script>
  const apiUrl = "/chat";

  function el(id){ return document.getElementById(id); }

  function addMsg(who, text){
    const box = el("chatbox");
    const div = document.createElement("div");
    div.className = "msg " + (who === "me" ? "me" : "bot");
    div.textContent = (who === "me" ? "You: " : "Assistant: ") + text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  function todayISO(){
    const d = new Date();
    const mm = String(d.getMonth()+1).padStart(2,"0");
    const dd = String(d.getDate()).padStart(2,"0");
    return `${d.getFullYear()}-${mm}-${dd}`;
  }

  function init(){
    // guests 1..20
    const g = el("guests");
    for(let i=1;i<=20;i++){
      const opt = document.createElement("option");
      opt.value = i; opt.textContent = i;
      g.appendChild(opt);
    }
    g.value = 2;
    el("date").value = todayISO();

    // initial message
    addMsg("bot", "Use the controls to check availability and book. Chat is optional.");
    // populate times immediately
    checkAvailability();
  }

  async function post(payload){
    const res = await fetch(apiUrl, {
      method:"POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify(payload)
    });
    if(!res.ok){
      throw new Error("Request failed");
    }
    return await res.json();
  }

  function setTimes(times){
    const t = el("time");
    t.innerHTML = "";
    if(!times || times.length === 0){
      const opt = document.createElement("option");
      opt.value = ""; opt.textContent = "No available times";
      t.appendChild(opt);
      t.value = "";
      return;
    }
    // store value as HH:MM in 24h by reading label back from server is hard;
    // so we will ask server again during booking with chosen label? No.
    // Instead, we use a hidden map: label->hh:mm from client calculation is unreliable.
    // We will request server-generated list in 24h format too? We'll keep it simple:
    // We send HH:MM 24h in value by converting from label using a small parser.
    // Server labels are "h:mm AM/PM". We'll parse to 24h.
    times.forEach(label => {
      const opt = document.createElement("option");
      opt.value = labelTo24(label);
      opt.textContent = label;
      t.appendChild(opt);
    });
    t.value = t.options[0].value;
  }

  function labelTo24(label){
    // label like "8:30 PM"
    const m = label.trim().match(/^(\d{1,2}):(\d{2})\s*(AM|PM)$/i);
    if(!m) return "";
    let h = parseInt(m[1],10);
    const mm = parseInt(m[2],10);
    const ap = m[3].toUpperCase();
    if(h === 12) h = 0;
    if(ap === "PM") h += 12;
    return String(h).padStart(2,"0") + ":" + String(mm).padStart(2,"0");
  }

  async function checkAvailability(){
    const payload = {
      session_id: el("session_id").value.trim() || "web-session",
      message: "",
      action: "availability",
      guests: parseInt(el("guests").value,10),
      date: el("date").value
    };
    addMsg("me", "Check availability");
    try{
      const data = await post(payload);
      addMsg("bot", data.reply);
      setTimes(data.available_times || []);
    }catch(e){
      addMsg("bot", "Error checking availability. Please retry.");
    }
  }

  async function book(){
    const payload = {
      session_id: el("session_id").value.trim() || "web-session",
      message: "",
      action: "book",
      guests: parseInt(el("guests").value,10),
      date: el("date").value,
      time: el("time").value, // 24h HH:MM
      name: el("name").value,
      phone: el("phone").value || null
    };
    addMsg("me", "Book");
    try{
      const data = await post(payload);
      addMsg("bot", data.reply);
      if(data.active_reservation && data.active_reservation.reservation_id){
        el("reservation_id").value = data.active_reservation.reservation_id;
      }
      // refresh available times after booking
      await checkAvailability();
    }catch(e){
      addMsg("bot", "Error booking. Please retry.");
    }
  }

  async function modify(){
    const payload = {
      session_id: el("session_id").value.trim() || "web-session",
      message: "",
      action: "modify",
      reservation_id: el("reservation_id").value,
      guests: parseInt(el("guests").value,10),
      date: el("date").value,
      time: el("time").value
    };
    addMsg("me", "Modify");
    try{
      const data = await post(payload);
      addMsg("bot", data.reply);
      // refresh times
      await checkAvailability();
    }catch(e){
      addMsg("bot", "Error modifying reservation. Please retry.");
    }
  }

  async function cancelRes(){
    const payload = {
      session_id: el("session_id").value.trim() || "web-session",
      message: "",
      action: "cancel",
      reservation_id: el("reservation_id").value
    };
    addMsg("me", "Cancel");
    try{
      const data = await post(payload);
      addMsg("bot", data.reply);
      // refresh times
      await checkAvailability();
    }catch(e){
      addMsg("bot", "Error cancelling reservation. Please retry.");
    }
  }

  async function menu(details){
    const payload = {
      session_id: el("session_id").value.trim() || "web-session",
      message: "",
      action: "menu",
      menu_details: details
    };
    addMsg("me", details ? "Menu (details)" : "Menu (short)");
    try{
      const data = await post(payload);
      addMsg("bot", data.reply);
    }catch(e){
      addMsg("bot", "Error loading menu. Please retry.");
    }
  }

  async function sendChat(){
    const payload = {
      session_id: el("session_id").value.trim() || "web-session",
      message: el("message").value || ""
    };
    addMsg("me", payload.message || "(empty)");
    el("message").value = "";
    try{
      const data = await post(payload);
      addMsg("bot", data.reply);
      if(data.available_times){ setTimes(data.available_times); }
      if(data.active_reservation && data.active_reservation.reservation_id){
        el("reservation_id").value = data.active_reservation.reservation_id;
      }
    }catch(e){
      addMsg("bot", "Error sending message. Please retry.");
    }
  }

  // auto-refresh times when date/guests change (simple UX)
  window.addEventListener("load", () => {
    init();
    el("date").addEventListener("change", checkAvailability);
    el("guests").addEventListener("change", checkAvailability);
  });
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(INDEX_HTML)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    s = get_session(req.session_id)
    text = (req.message or "").strip().lower()

    # ---------- UI-FIRST ACTIONS ----------
    if req.action == "menu" or "menu" in text:
        details = bool(req.menu_details) or any(k in text for k in ["details", "description", "ingredients"])
        return ChatResponse(reply=menu_response(details))

    if req.action == "availability":
        d = parse_date_iso(req.date)
        g = req.guests
        if not d:
            return ChatResponse(reply="Select a date to check availability.")
        if not g:
            return ChatResponse(reply="Select number of guests to check availability.")
        slots = engine.availability(d, g)
        if not slots:
            return ChatResponse(reply="No available times for the selected date and party size.", available_times=[])
        return ChatResponse(reply="Available times shown.", available_times=[fmt_time(t) for t in slots])

    if req.action == "book":
        d = parse_date_iso(req.date)
        t = parse_time_hhmm(req.time)
        g = req.guests
        name = (req.name or s.name or "").strip()
        phone = (req.phone or s.phone)

        if not name:
            return ChatResponse(reply="Enter a name to place the reservation.")
        if not d or not t or not g:
            return ChatResponse(reply="Select guests, date, and time to book.")

        try:
            r = engine.create(name=name, phone=phone, party_size=g, d=d, t=t)
        except ValueError:
            slots = engine.availability(d, g)
            return ChatResponse(
                reply="That time is no longer available. Please choose another available time.",
                available_times=[fmt_time(x) for x in slots],
            )

        s.name = s.name or name
        s.phone = s.phone or phone
        s.last_reservation_id = r.reservation_id

        return ChatResponse(reply=reservation_summary(r), active_reservation=serialize_reservation(r))

    if req.action == "modify":
        rid = (req.reservation_id or s.last_reservation_id or "").strip().upper()
        if not rid:
            return ChatResponse(reply="Provide a reservation reference to modify (e.g., R-XXXXXXXXXX).")
        r0 = engine.get(rid)
        if not r0:
            return ChatResponse(reply="Reservation not found. Check the reference and try again.")

        d = parse_date_iso(req.date) or r0.reservation_date
        t = parse_time_hhmm(req.time) or r0.reservation_time
        g = req.guests or r0.party_size

        try:
            r = engine.modify(rid, party_size=g, d=d, t=t)
        except ValueError:
            slots = engine.availability(d, g)
            return ChatResponse(
                reply="That update is not available. Please choose another available time.",
                available_times=[fmt_time(x) for x in slots],
            )

        s.last_reservation_id = r.reservation_id
        return ChatResponse(
            reply=reservation_summary(r, heading="Reservation updated."),
            active_reservation=serialize_reservation(r),
        )

    if req.action == "cancel":
        rid = (req.reservation_id or s.last_reservation_id or "").strip().upper()
        if not rid:
            return ChatResponse(reply="Provide a reservation reference to cancel (e.g., R-XXXXXXXXXX).")
        try:
            r = engine.cancel(rid)
        except KeyError:
            return ChatResponse(reply="Reservation not found. Check the reference and try again.")

        if s.last_reservation_id == rid:
            s.last_reservation_id = None
        return ChatResponse(reply=f"Reservation cancelled.\n- Reference: {r.reservation_id}")

    # ---------- CHAT FALLBACK (kept strict + production-like) ----------
    # We do NOT pretend to answer everything outside reservations/menu.
    if any(k in text for k in ["hi", "hello", "hey"]):
        return ChatResponse(reply="How can I help? Use the controls to check availability, book, modify, cancel, or view the menu.")

    if "available" in text or "availability" in text:
        return ChatResponse(reply="Use 'Check availability' with guests and date to see available times.")

    if any(k in text for k in ["book", "reserve", "reservation"]):
        return ChatResponse(reply="Use 'Book' with guests, date, time, and name to confirm a reservation.")

    if any(k in text for k in ["change", "modify", "reschedule", "update"]):
        return ChatResponse(reply="Use 'Modify' with your reservation reference and the new details.")

    if "cancel" in text:
        return ChatResponse(reply="Use 'Cancel' with your reservation reference.")

    return ChatResponse(
        reply="I can help with table availability, reservations (book/modify/cancel), or the menu. Please use the controls on the left."
    )


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
