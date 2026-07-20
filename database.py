# database.py
# MongoDB connection using motor (async)

import os
from datetime import datetime
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("MONGO_DB",  "a2a_hiring")

# Global client — initialized once on startup
_client = None
_db     = None


def get_db():
    global _client, _db
    if _client is None:
        _client = AsyncIOMotorClient(MONGO_URI)
        _db     = _client[DB_NAME]
    return _db


async def ping():
    db = get_db()
    await db.client.admin.command("ping")
    return True


async def save_application(data: dict) -> str:
    db = get_db()
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()
    result = await db["applications"].insert_one(data)
    return str(result.inserted_id)


async def get_all_applications(limit: int = 100) -> list:
    db = get_db()
    cursor = db["applications"].find({}).sort("created_at", -1).limit(limit)
    docs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        docs.append(doc)
    return docs


async def get_application_by_email(email: str):
    db = get_db()
    doc = await db["applications"].find_one({"email": email})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def get_stats() -> dict:
    db = get_db()
    col = db["applications"]
    total       = await col.count_documents({})
    shortlisted = await col.count_documents({"decision": "SHORTLISTED"})
    waitlisted  = await col.count_documents({"decision": "WAITLISTED"})
    rejected    = await col.count_documents({"decision": "REJECTED"})
    scheduled   = await col.count_documents({"interview_scheduled": True})
    return {
        "total": total,
        "shortlisted": shortlisted,
        "waitlisted": waitlisted,
        "rejected": rejected,
        "interviews_scheduled": scheduled,
    }


# ── Jobs Collection ────────────────────────────────────────────────────────────

async def create_job(data: dict) -> str:
    db = get_db()
    data["created_at"] = datetime.utcnow()
    data["updated_at"] = datetime.utcnow()
    data["active"]     = True
    result = await db["jobs"].insert_one(data)
    return str(result.inserted_id)


async def get_all_jobs() -> list:
    db = get_db()
    cursor = db["jobs"].find({"active": True}).sort("created_at", -1)
    docs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        docs.append(doc)
    return docs


async def get_job_by_id(job_id: str) -> dict | None:
    from bson import ObjectId
    db = get_db()
    try:
        doc = await db["jobs"].find_one({"_id": ObjectId(job_id)})
    except Exception:
        doc = await db["jobs"].find_one({"job_id": job_id})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def update_job(job_id: str, data: dict) -> bool:
    from bson import ObjectId
    db = get_db()
    data["updated_at"] = datetime.utcnow()
    result = await db["jobs"].update_one({"_id": ObjectId(job_id)}, {"$set": data})
    return result.modified_count > 0


async def delete_job(job_id: str) -> bool:
    from bson import ObjectId
    db = get_db()
    result = await db["jobs"].update_one({"_id": ObjectId(job_id)}, {"$set": {"active": False}})
    return result.modified_count > 0


async def get_job_stats(job_id: str) -> dict:
    db = get_db()
    col = db["applications"]
    total       = await col.count_documents({"job_id": job_id})
    shortlisted = await col.count_documents({"job_id": job_id, "decision": "SHORTLISTED"})
    waitlisted  = await col.count_documents({"job_id": job_id, "decision": "WAITLISTED"})
    rejected    = await col.count_documents({"job_id": job_id, "decision": "REJECTED"})
    return {"total": total, "shortlisted": shortlisted, "waitlisted": waitlisted, "rejected": rejected}


# ── Company / Auth Collection ──────────────────────────────────────────────────

async def create_company(data: dict) -> str:
    try:
        existing = await get_company_by_email(data["email"])
        if existing:
            return str(existing["_id"])
        db = get_db()
        data["created_at"] = datetime.utcnow()
        data["active"]     = True
        result = await db["companies"].insert_one(data)
        return str(result.inserted_id)
    except Exception as e:
        print(f"Error creating company: {e}")
        return None

async def get_company_by_email(email: str) -> dict | None:
    try: 
        print(f"Fetching company by email: {email}")
        db = get_db()
        return await db["companies"].find_one({"email": email.lower()})
    except Exception as e:
        print(f"Error fetching company by email: {e}")
        return None

async def get_company_by_id(company_id: str) -> dict | None:
    from bson import ObjectId
    db = get_db()
    try:
        doc = await db["companies"].find_one({"_id": ObjectId(company_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
    except Exception:
        return None

async def get_all_applications_for_company(company_id: str) -> list:
    db = get_db()
    cursor = db["applications"].find({"company_id": company_id}).sort("created_at", -1)
    docs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        docs.append(doc)
    return docs

async def get_stats_for_company(company_id: str) -> dict:
    db   = get_db()
    col  = db["applications"]
    total       = await col.count_documents({"company_id": company_id})
    shortlisted = await col.count_documents({"company_id": company_id, "decision": "SHORTLISTED"})
    waitlisted  = await col.count_documents({"company_id": company_id, "decision": "WAITLISTED"})
    rejected    = await col.count_documents({"company_id": company_id, "decision": "REJECTED"})
    interviews  = await col.count_documents({"company_id": company_id, "interview_scheduled": True})
    return {
        "total": total, "shortlisted": shortlisted,
        "waitlisted": waitlisted, "rejected": rejected,
        "interviews_scheduled": interviews,
    }

async def get_jobs_for_company(company_id: str) -> list:
    db = get_db()
    cursor = db["jobs"].find({"company_id": company_id, "active": True}).sort("created_at", -1)
    docs = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        docs.append(doc)
    return docs

async def get_application_by_email_and_company(email: str, company_id: str) -> dict | None:
    db = get_db()
    return await db["applications"].find_one({"email": email, "company_id": company_id})