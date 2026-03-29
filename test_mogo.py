import os
from dotenv import load_dotenv
from pymongo import MongoClient
import certifi

load_dotenv()

uri = os.getenv("MONGO_URI")

if not uri:
    print("❌ MONGO_URI not found in .env")
    exit()

try:
    if "mongodb+srv" in uri:
        client = MongoClient(uri, tlsCAFile=certifi.where())
    else:
        client = MongoClient(uri)

    # Test connection
    client.admin.command("ping")
    print("✅ Connected to MongoDB successfully!")

    # Safe DB selection
    db = client.get_default_database()
    if db is None:
        db = client["habit_tracker"]

    print(f"📦 Using database: {db.name}")

    # Test write
    result = db.test_collection.insert_one({"test": "connection_ok"})
    print("✅ Test document inserted:", result.inserted_id)

    doc = db.test_collection.find_one({"_id": result.inserted_id})
    print("✅ Read back document:", doc)

    print("\n🎉 Everything works perfectly!")

except Exception as e:
    print("❌ Connection failed:")
    print(e)