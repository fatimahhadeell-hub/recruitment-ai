import datetime
from typing import Optional
import pymongo
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config.settings import settings

class DatabaseManager:
    def __init__(self):
        self._sync_client  = None
        self._async_client = None
        self._sync_db      = None
        self._async_db     = None

    def connect(self) -> None:
        logger.info(f"Connecting to MongoDB at {settings.MONGODB_URI} ...")
        try:
            self._sync_client = MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000, tlsAllowInvalidCertificates=True)
            self._sync_client.admin.command("ping")
            self._sync_db = self._sync_client[settings.MONGODB_DATABASE]
            self._async_client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000, tlsAllowInvalidCertificates=True)
            self._async_db = self._async_client[settings.MONGODB_DATABASE]
            logger.success(f"Connected to MongoDB. Database: '{settings.MONGODB_DATABASE}'")
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logger.error(f"Could not connect to MongoDB: {e}")
            raise SystemExit(1)

    def disconnect(self) -> None:
        if self._sync_client:
            self._sync_client.close()
        if self._async_client:
            self._async_client.close()
        logger.info("MongoDB connections closed.")

    def is_connected(self) -> bool:
        if not self._sync_client:
            return False
        try:
            self._sync_client.admin.command("ping")
            return True
        except Exception:
            return False

    def _require_sync(self):
        if self._sync_db is None:
            raise RuntimeError("Call db_manager.connect() first.")

    @property
    def jobs(self):
        self._require_sync()
        return self._sync_db[settings.COLLECTION_JOBS]

    @property
    def candidates(self):
        self._require_sync()
        return self._sync_db[settings.COLLECTION_CANDIDATES]

    @property
    def scores(self):
        self._require_sync()
        return self._sync_db[settings.COLLECTION_SCORES]

    @property
    def interviews(self):
        self._require_sync()
        return self._sync_db[settings.COLLECTION_INTERVIEWS]

    @property
    def notifications(self):
        self._require_sync()
        return self._sync_db[settings.COLLECTION_NOTIFICATIONS]

    @property
    def system_config(self):
        self._require_sync()
        return self._sync_db[settings.COLLECTION_CONFIG]

    @property
    def async_jobs(self):
        return self._async_db[settings.COLLECTION_JOBS]

    @property
    def async_candidates(self):
        return self._async_db[settings.COLLECTION_CANDIDATES]

    @property
    def async_scores(self):
        return self._async_db[settings.COLLECTION_SCORES]

    @property
    def async_interviews(self):
        return self._async_db[settings.COLLECTION_INTERVIEWS]

    @property
    def async_notifications(self):
        return self._async_db[settings.COLLECTION_NOTIFICATIONS]

    @property
    def async_system_config(self):
        return self._async_db[settings.COLLECTION_CONFIG]

    def create_indexes(self) -> None:
        logger.info("Creating database indexes...")
        self.jobs.create_index([("status", pymongo.ASCENDING)], name="idx_jobs_status")
        self.candidates.create_index([("job_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)], name="idx_candidates_job_status")
        self.candidates.create_index([("google_drive_file_id", pymongo.ASCENDING)], name="idx_candidates_drive_file", sparse=True)
        self.candidates.create_index([("email", pymongo.ASCENDING)], name="idx_candidates_email", sparse=True)
        self.scores.create_index([("candidate_id", pymongo.ASCENDING), ("job_id", pymongo.ASCENDING)], name="idx_scores_candidate_job", unique=True)
        self.interviews.create_index([("candidate_id", pymongo.ASCENDING), ("job_id", pymongo.ASCENDING)], name="idx_interviews_candidate_job", unique=True)
        self.notifications.create_index([("status", pymongo.ASCENDING)], name="idx_notifications_status")
        self.system_config.create_index([("key", pymongo.ASCENDING)], name="idx_config_key", unique=True)
        logger.success("Database indexes created.")

    def seed_system_config(self) -> None:
        logger.info("Seeding system_config...")
        defaults = [
            {"key": "default_shortlist_threshold", "value": settings.SHORTLIST_THRESHOLD, "description": "Minimum score to shortlist", "editable_in_ui": True},
            {"key": "ollama_model",                "value": settings.OLLAMA_MODEL,         "description": "Ollama model name",          "editable_in_ui": True},
            {"key": "min_tenure_months",           "value": settings.MIN_TENURE_MONTHS,    "description": "Min months per role",        "editable_in_ui": True},
            {"key": "smtp_enabled",                "value": settings.SMTP_ENABLED,         "description": "Enable email sending",       "editable_in_ui": True},
            {"key": "app_version",                 "value": settings.APP_VERSION,          "description": "App version",                "editable_in_ui": False},
            {"key": "db_initialised_at",           "value": datetime.datetime.utcnow().isoformat(), "description": "First init time", "editable_in_ui": False},
        ]
        inserted = 0
        for entry in defaults:
            result = self.system_config.update_one(
                {"key": entry["key"]},
                {"$setOnInsert": {**entry, "created_at": datetime.datetime.utcnow(), "updated_at": datetime.datetime.utcnow()}},
                upsert=True
            )
            if result.upserted_id:
                inserted += 1
        logger.success(f"System config seeded. Inserted: {inserted} new entries.")

    def get_config_value(self, key: str, default=None):
        doc = self.system_config.find_one({"key": key}, {"value": 1})
        return doc["value"] if doc else default

    def set_config_value(self, key: str, value) -> None:
        self.system_config.update_one(
            {"key": key},
            {"$set": {"value": value, "updated_at": datetime.datetime.utcnow()}},
            upsert=True
        )

    def get_stats(self) -> dict:
        return {
            "jobs":          {"total": self.jobs.count_documents({}), "active": self.jobs.count_documents({"status": "active"})},
            "candidates":    {"total": self.candidates.count_documents({}), "shortlisted": self.candidates.count_documents({"status": "shortlisted"})},
            "scores":        {"total": self.scores.count_documents({})},
            "interviews":    {"total": self.interviews.count_documents({})},
            "notifications": {"total": self.notifications.count_documents({})},
        }

db_manager = DatabaseManager()

async def get_async_db() -> AsyncIOMotorDatabase:
    if db_manager._async_db is None:
        raise RuntimeError("db_manager.connect() not called.")
    yield db_manager._async_db
