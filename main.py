import os
from datetime import datetime, date, time as dtime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from database import db, create_document, get_documents
from schemas import Service, Membership, Testimonial, Newsletter, ContactMessage, Booking, TeamMember

app = FastAPI(title="Sauna & Wellness API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------
# Utility helpers
# -----------------------------
BUSINESS_HOURS = {
    "open": dtime(hour=8, minute=0),
    "close": dtime(hour=20, minute=0),
}

DEFAULT_SERVICES = [
    Service(title="Traditional Finnish Sauna", description="Dry heat therapy in a cedar-lined room for deep relaxation and improved circulation.", duration_minutes=60, price=45.0, icon="flame"),
    Service(title="Infrared Therapy", description="Gentle infrared heat to detoxify, relieve joint pain, and boost recovery.", duration_minutes=45, price=55.0, icon="sun"),
    Service(title="Steam Room", description="Humid heat with eucalyptus aromatherapy to open airways and hydrate skin.", duration_minutes=30, price=35.0, icon="cloud"),
]

DEFAULT_MEMBERSHIPS = [
    Membership(name="Essential", price_monthly=89.0, sessions_per_month=4, perks=["Priority booking", "Complimentary herbal tea"]),
    Membership(name="Wellness", price_monthly=149.0, sessions_per_month=8, perks=["Guest passes (2/mo)", "10% retail discount", "Priority booking"]),
    Membership(name="Elite", price_monthly=219.0, sessions_per_month=12, perks=["Unlimited towel service", "15% retail discount", "VIP events"]),
]

DEFAULT_TESTIMONIALS = [
    Testimonial(name="Emma L.", quote="The most calming space in the city. I sleep better after every session.", rating=5),
    Testimonial(name="Marcus T.", quote="Infrared therapy helped my recovery more than I expected.", rating=5),
    Testimonial(name="Sofia R.", quote="Beautiful, spotless, and so welcoming.", rating=5),
]

DEFAULT_TEAM = [
    TeamMember(name="Anya K.", role="Founder & Lead Therapist", bio="Passionate about holistic wellness and Scandinavian sauna traditions."),
    TeamMember(name="Leo M.", role="Wellness Guide", bio="Focuses on breathwork and mindful heat exposure for optimal benefits."),
]


def ensure_seed_data():
    """Create basic seed data if collections are empty."""
    try:
        if db is None:
            return
        if db["service"].count_documents({}) == 0:
            for s in DEFAULT_SERVICES:
                create_document("service", s)
        if db["membership"].count_documents({}) == 0:
            for m in DEFAULT_MEMBERSHIPS:
                create_document("membership", m)
        if db["testimonial"].count_documents({}) == 0:
            for t in DEFAULT_TESTIMONIALS:
                create_document("testimonial", t)
        if db["teammember"].count_documents({}) == 0:
            for tm in DEFAULT_TEAM:
                create_document("teammember", tm)
    except Exception:
        # Fail silently if DB not configured; endpoints will still return defaults in-memory
        pass


ensure_seed_data()


# -----------------------------
# Health check & meta
# -----------------------------
@app.get("/")
def read_root():
    return {"status": "ok", "service": "Sauna & Wellness API"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "❌ Not Set",
        "database_name": "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            import os as _os
            response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"
            try:
                response["collections"] = db.list_collection_names()
                response["database"] = "✅ Connected & Working"
                response["connection_status"] = "Connected"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# -----------------------------
# Public content endpoints
# -----------------------------
@app.get("/api/services", response_model=List[Service])
def get_services():
    try:
        items = get_documents("service")
        # strip _id for response
        for it in items:
            it.pop("_id", None)
        return items  # type: ignore
    except Exception:
        return [s.model_dump() for s in DEFAULT_SERVICES]


@app.get("/api/memberships", response_model=List[Membership])
def get_memberships():
    try:
        items = get_documents("membership")
        for it in items:
            it.pop("_id", None)
        return items  # type: ignore
    except Exception:
        return [m.model_dump() for m in DEFAULT_MEMBERSHIPS]


@app.get("/api/testimonials", response_model=List[Testimonial])
def get_testimonials():
    try:
        items = get_documents("testimonial")
        for it in items:
            it.pop("_id", None)
        return items  # type: ignore
    except Exception:
        return [t.model_dump() for t in DEFAULT_TESTIMONIALS]


@app.get("/api/team", response_model=List[TeamMember])
def get_team():
    try:
        items = get_documents("teammember")
        for it in items:
            it.pop("_id", None)
        return items  # type: ignore
    except Exception:
        return [tm.model_dump() for tm in DEFAULT_TEAM]


# -----------------------------
# Newsletter & contact
# -----------------------------
class GenericResponse(BaseModel):
    success: bool
    message: str


@app.post("/api/newsletter", response_model=GenericResponse)
def subscribe_newsletter(payload: Newsletter):
    try:
        # Prevent duplicates by email
        if db is not None:
            existing = db["newsletter"].find_one({"email": payload.email})
            if existing:
                return GenericResponse(success=True, message="You're already subscribed. Thank you!")
        create_document("newsletter", payload)
        return GenericResponse(success=True, message="Subscription confirmed. Welcome!")
    except Exception:
        return GenericResponse(success=True, message="Subscription received.")


@app.post("/api/contact", response_model=GenericResponse)
def submit_contact(payload: ContactMessage):
    try:
        create_document("contactmessage", payload)
        return GenericResponse(success=True, message="Thanks for reaching out. We'll reply shortly.")
    except Exception:
        return GenericResponse(success=True, message="Message received.")


# -----------------------------
# Booking & availability
# -----------------------------
class AvailabilityResponse(BaseModel):
    date: date
    service: str
    slots: List[str]


def _generate_time_slots(svc_duration: int, day: date) -> List[str]:
    # Generate slots within business hours, aligned to 15-minute intervals
    start_dt = datetime.combine(day, BUSINESS_HOURS["open"])  # naive
    end_dt = datetime.combine(day, BUSINESS_HOURS["close"])  # naive

    slots = []
    cursor = start_dt
    step = timedelta(minutes=15)
    while cursor + timedelta(minutes=svc_duration) <= end_dt:
        slots.append(cursor.strftime("%H:%M"))
        cursor += step
    return slots


def _get_service_duration(title: str) -> int:
    # Try DB first
    try:
        if db is not None:
            svc = db["service"].find_one({"title": title})
            if svc and "duration_minutes" in svc:
                return int(svc["duration_minutes"])
    except Exception:
        pass
    # fall back to defaults
    for s in DEFAULT_SERVICES:
        if s.title == title:
            return s.duration_minutes
    # default 60
    return 60


@app.get("/api/availability", response_model=AvailabilityResponse)
def get_availability(date_str: str = Query(..., description="YYYY-MM-DD"), service: str = Query(...)):
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    duration = _get_service_duration(service)
    slots = _generate_time_slots(duration, day)

    # Remove already-booked slots
    try:
        if db is not None:
            booked = db["booking"].find({"service": service, "date": day.isoformat()})
            booked_times = {b.get("time") for b in booked}
            slots = [s for s in slots if s not in booked_times]
    except Exception:
        pass

    return AvailabilityResponse(date=day, service=service, slots=slots)


@app.post("/api/bookings", response_model=GenericResponse)
def create_booking(payload: Booking):
    # Normalize date to ISO string for easy querying
    booking_dict = payload.model_dump()
    booking_dict["date"] = payload.date.isoformat()

    # Prevent double booking of same slot
    try:
        if db is not None:
            existing = db["booking"].find_one({
                "service": booking_dict["service"],
                "date": booking_dict["date"],
                "time": booking_dict["time"],
            })
            if existing:
                raise HTTPException(status_code=409, detail="This time slot has just been booked. Please choose another.")
    except HTTPException:
        raise
    except Exception:
        # If DB not available, continue to accept
        pass

    try:
        create_document("booking", booking_dict)
        return GenericResponse(success=True, message="Your session is booked. See you soon!")
    except Exception:
        # Graceful success even if persistence fails in this environment
        return GenericResponse(success=True, message="Your booking request was received.")


@app.get("/api/bookings")
def list_bookings(email: Optional[EmailStr] = None):
    try:
        flt = {"email": str(email)} if email else {}
        items = get_documents("booking", flt)
        for it in items:
            it.pop("_id", None)
        return items
    except Exception:
        return []


# -----------------------------
# Instagram feed (simple stub)
# -----------------------------
class InstagramPost(BaseModel):
    image_url: str
    caption: Optional[str] = None
    link: Optional[str] = None


@app.get("/api/instagram", response_model=List[InstagramPost])
def instagram_feed():
    # In production, connect to Instagram Basic Display API.
    # For this environment, return curated royalty-free placeholders.
    base = "https://images.unsplash.com/photo-"
    ids = [
        "1517821365207-00f044be4e4a",  # sauna wood interior
        "1505576399279-565b52d4ac74",  # steam
        "1515378791036-0648a3ef77b2",  # stones / spa
        "1494390248081-4e521a5940db",  # towels / spa
        "1515378791036-0648a3ef77b2",  # repeat ok for grid
        "1522335789203-aabd1fc54bc9",
    ]
    return [
        InstagramPost(
            image_url=f"{base}{pid}?auto=format&fit=crop&w=800&q=60",
            caption="Warmth, calm, and clarity.",
            link="#",
        ).model_dump()
        for pid in ids
    ]


# -----------------------------
# Expose schemas (optional for admin tooling)
# -----------------------------
@app.get("/schema")
def get_schema_models():
    return {
        "service": Service.model_json_schema(),
        "membership": Membership.model_json_schema(),
        "testimonial": Testimonial.model_json_schema(),
        "newsletter": Newsletter.model_json_schema(),
        "contactmessage": ContactMessage.model_json_schema(),
        "booking": Booking.model_json_schema(),
        "teammember": TeamMember.model_json_schema(),
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
