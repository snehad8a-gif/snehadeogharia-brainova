import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Configuration
# User can set USE_CLOUD_DB=true in .env to enable Mongo
USE_CLOUD = os.getenv("USE_CLOUD_DB", "false").lower() == "true"
BACKEND_NAME = "SQLite"

try:
    if USE_CLOUD:
        from src.db_mongo import *
        # Verify connection explicitly
        if not init_db():
            raise Exception("Could not connect to MongoDB.")
        BACKEND_NAME = "MongoDB"
    else:
        raise ImportError("Cloud DB disabled.")
        
except Exception as e:
    # Fallback to Local
    if USE_CLOUD:
        print(f"⚠️ Cloud DB Connection Failed ({e}). Falling back to SQLite.")
    from src.db_sqlite import *
    BACKEND_NAME = "SQLite"

# We expose everything from the selected backend.
# The app imports from here, so it gets the functions from the chosen module.
