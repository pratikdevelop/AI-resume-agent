# test_mongo.py
# Run: python test_mongo.py
# Tests your MongoDB Atlas connection

from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("MONGO_DB", "a2a_hiring")

print("Connecting to MongoDB...")
print(f"URI: {MONGO_URI[:40]}...")

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    
    # Force connection
    info = client.server_info()
    print(f"\nConnected! MongoDB version: {info['version']}")

    # Create test document
    db  = client[DB_NAME]
    col = db["test"]
    col.insert_one({"test": "hello", "from": "A2A pipeline"})
    print(f"Test document inserted into '{DB_NAME}.test'")

    # Read it back
    doc = col.find_one({"test": "hello"})
    print(f"Read back: {doc}")

    # Cleanup
    col.drop()
    print("Test collection cleaned up")

    print("\nMongoDB Atlas is working perfectly!")

except Exception as e:
    print(f"\nConnection failed: {e}")
    print("\nCheck:")
    print("  1. MONGO_URI is correct in your .env")
    print("  2. Atlas Network Access allows 0.0.0.0/0")
    print("  3. Username/password are correct in the connection string")