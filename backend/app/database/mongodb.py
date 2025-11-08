from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from config import settings
from typing import Optional


class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    sync_client: Optional[MongoClient] = None


mongodb = MongoDB()


async def connect_to_mongo():
    """Connect to MongoDB Atlas"""
    mongodb.client = AsyncIOMotorClient(settings.mongodb_uri)
    mongodb.sync_client = MongoClient(settings.mongodb_uri)
    print("✅ Connected to MongoDB Atlas")


async def close_mongo_connection():
    """Close MongoDB connection"""
    if mongodb.client:
        mongodb.client.close()
        print("👋 Disconnected from MongoDB Atlas")


def get_mongo_db():
    """Get MongoDB database instance"""
    if mongodb.sync_client is None:
        # Initialize connection if not already done
        if settings.mongodb_uri:
            mongodb.sync_client = MongoClient(settings.mongodb_uri)
            print("✅ MongoDB connection initialized")
        else:
            raise ConnectionError("MongoDB URI not configured. Set MONGODB_URI in environment.")
    return mongodb.sync_client[settings.mongodb_db_name]


async def get_async_mongo_db():
    """Get async MongoDB database instance"""
    if mongodb.client is None:
        # Initialize connection if not already done
        if settings.mongodb_uri:
            mongodb.client = AsyncIOMotorClient(settings.mongodb_uri)
            if mongodb.sync_client is None:
                mongodb.sync_client = MongoClient(settings.mongodb_uri)
            print("✅ MongoDB async connection initialized")
        else:
            raise ConnectionError("MongoDB URI not configured. Set MONGODB_URI in environment.")
    return mongodb.client[settings.mongodb_db_name]

