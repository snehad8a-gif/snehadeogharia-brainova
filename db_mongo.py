import streamlit as st
import pandas as pd
from datetime import datetime
import os
import json
from dotenv import load_dotenv
from pymongo import MongoClient
from bson.objectid import ObjectId
from src.gamification import calculate_xp_gain, get_level_info

load_dotenv()

# Global Client
CLIENT = None
DB = None

import certifi

def get_db():
    global CLIENT, DB
    if DB is None:
        uri = os.getenv("MONGO_URI")
        if not uri:
            st.error("MONGO_URI not found in .env")
            return None
        try:
            # Added tlsCAFile for Windows SSL handshake issues
            CLIENT = MongoClient(uri, tlsCAFile=certifi.where())
            # Default DB name or from URI
            # Safe way to get DB name from cluster URI
            db_name = "habit_tracker" # Default
            if "/" in uri.split("://")[-1]:
                db_name = uri.split("/")[-1].split("?")[0] or "habit_tracker"
            DB = CLIENT[db_name]
        except Exception as e:
            st.error(f"Failed to connect to MongoDB: {e}")
            return None
    return DB

# --- INIT ---
def init_db():
    """Mongo initializes on write, but we can verify connection."""
    if get_db() is not None:
        return True
    return False

def init_gamification_db():
    """Ensure user_progress doc exists."""
    db = get_db()
    if db is None: return
    
    # Check for user_progress (singleton with _id=1 to match sqlite logic)
    # Using _id=1 for simplicity
    if not db.user_progress.find_one({"_id": 1}):
        db.user_progress.insert_one({
            "_id": 1,
            "total_xp": 0,
            "unlocked_badges": []
        })

# --- GAMIFICATION ---
def get_user_progress():
    db = get_db()
    res = db.user_progress.find_one({"_id": 1})
    if res:
        return {"total_xp": res.get("total_xp", 0), "unlocked_badges": res.get("unlocked_badges", [])}
    return {"total_xp": 0, "unlocked_badges": []}

def update_user_progress(xp_delta, new_badges=None):
    db = get_db()
    curr = get_user_progress()
    new_xp = curr['total_xp'] + xp_delta
    badges = curr['unlocked_badges']
    
    if new_badges:
        for b in new_badges:
            if b not in badges:
                badges.append(b)
    
    db.user_progress.update_one(
        {"_id": 1},
        {"$set": {"total_xp": new_xp, "unlocked_badges": badges}},
        upsert=True
    )
    return new_xp, badges

# Automatically init when imported
init_db()
init_gamification_db()

# --- HABITS ---
def load_habits(active_only=True):
    db = get_db()
    query = {"is_active": 1} if active_only else {}
    
    cursor = db.habits.find(query).sort("created_at", -1)
    df = pd.DataFrame(list(cursor))
    
    if df.empty:
        return pd.DataFrame(columns=['id', 'name', 'category', 'frequency_type', 'frequency_value', 'target_value', 'target_unit', 'created_at', 'is_active'])
    
    # Map _id to id (string)
    df['id'] = df['_id'].astype(str)
    return df

def load_logs(days_back=30):
    db = get_db()
    # Simple date filter? Mongo dates are objects or strings.
    # We store dates as strings "YYYY-MM-DD".
    # Filter: >= date string.
    start_date = (pd.Timestamp.now() - pd.Timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    cursor = db.logs.find({"date": {"$gte": start_date}}).sort("date", -1)
    df = pd.DataFrame(list(cursor))
    
    if df.empty:
        return pd.DataFrame(columns=['id', 'habit_id', 'date', 'value', 'status', 'notes', 'timestamp'])
    
    df['id'] = df['_id'].astype(str)
    return df

def add_habit(habit_data):
    db = get_db()
    habit_data['created_at'] = datetime.now()
    habit_data['is_active'] = 1
    # Ensure target_value default
    if 'target_value' not in habit_data: habit_data['target_value'] = 1
    
    try:
        db.habits.insert_one(habit_data)
        return True
    except Exception as e:
        st.error(f"Mongo Error: {e}")
        return False

def edit_habit(habit_id, updated_data):
    db = get_db()
    try:
        db.habits.update_one(
            {"_id": ObjectId(habit_id)},
            {"$set": updated_data}
        )
        return True
    except Exception as e:
        st.error(f"Mongo Error: {e}")
        return False

def delete_habit(habit_id):
    db = get_db()
    try:
        db.habits.update_one(
            {"_id": ObjectId(habit_id)},
            {"$set": {"is_active": 0}}
        )
        return True
    except Exception as e:
        st.error(f"Mongo Error: {e}")
        return False

def log_habit_completion(habit_id_str, date, status="Completed", notes="", value=1):
    db = get_db()
    # Check duplicate
    # Log stores habit_id as string to match
    if db.logs.find_one({"habit_id": habit_id_str, "date": str(date)}):
        return False, {}
    
    log_entry = {
        "habit_id": habit_id_str,
        "date": str(date),
        "status": status,
        "notes": notes,
        "value": value,
        "timestamp": datetime.now()
    }
    
    try:
        db.logs.insert_one(log_entry)
        
        # --- GAMIFICATION ---
        # Fetch habit needed for streaks
        habit = db.habits.find_one({"_id": ObjectId(habit_id_str)})
        if habit:
            # Need DF for analytics
            logs_cursor = db.logs.find({"habit_id": habit_id_str})
            habit_logs_df = pd.DataFrame(list(logs_cursor))
            if habit_logs_df.empty:
                # Should not happen as we just inserted
                habit_logs_df = pd.DataFrame([log_entry]) # minimal
            
            # Use analytics
            from src.analytics import calculate_streaks
            # calculate_streaks expects habit dict (ok) and logs DF (ok)
            # Ensure DF columns match what analytics expects
            # Analytics expects 'date' column.
            current_streak = calculate_streaks(habit, habit_logs_df)
            prev_streak = max(0, current_streak - 1)
            
            xp = calculate_xp_gain(current_streak, prev_streak)
            
            # Badges
            candidate_badges = []
            curr_progress = get_user_progress()
            existing_badges = curr_progress['unlocked_badges']
            
            if current_streak == 7: candidate_badges.append('week_warrior')
            if current_streak == 30: candidate_badges.append('month_master')
            if curr_progress['total_xp'] == 0: candidate_badges.append('first_step')
            
            # Hat Trick
            day_count = db.logs.count_documents({"date": str(date)})
            if day_count == 3: candidate_badges.append('hat_trick')
            
            new_badges = [b for b in candidate_badges if b not in existing_badges]
            
            new_xp_total, _ = update_user_progress(xp, new_badges)
            
            curr_lvl, _ = get_level_info(new_xp_total)
            prev_lvl, _ = get_level_info(new_xp_total - xp)
            level_up = (curr_lvl['level'] > prev_lvl['level'])
            
            return True, {
                "xp_earned": xp,
                "level_up": level_up,
                "current_level": curr_lvl,
                "new_badges": new_badges
            }
            
        return True, {"xp_earned": 0}
        
    except Exception as e:
        st.error(f"Mongo Error: {e}")
        return False, {}

def get_habit_stats(habit_id):
    db = get_db()
    logs = list(db.logs.find({"habit_id": habit_id}))
    if not logs: return None
    
    count = len(logs)
    last_log = max(l['date'] for l in logs)
    return {"count": count, "last_log": last_log}

# --- REMINDERS & PROJECTS ---
def add_reminder(text, priority='low'):
    get_db().reminders.insert_one({
        "text": text, "priority": priority, "is_completed": 0, "created_at": datetime.now()
    })
    return True

def get_reminders(pending_only=True):
    query = {"is_completed": 0} if pending_only else {}
    cursor = get_db().reminders.find(query).sort("created_at", -1)
    df = pd.DataFrame(list(cursor))
    if df.empty: return pd.DataFrame(columns=['id', 'text', 'priority', 'is_completed', 'created_at'])
    df['id'] = df['_id'].astype(str)
    return df

def update_reminder_status(rid, is_completed=True):
    val = 1 if is_completed else 0
    res = get_db().reminders.update_one({"_id": ObjectId(rid)}, {"$set": {"is_completed": val}})
    return res.modified_count > 0

def delete_reminder(rid):
    res = get_db().reminders.delete_one({"_id": ObjectId(rid)})
    return res.deleted_count > 0

def add_project(text, description, priority='low'):
    get_db().projects.insert_one({
        "text": text, "description": description, "priority": priority, 
        "is_completed": 0, "created_at": datetime.now()
    })
    return True

def get_projects(pending_only=True):
    query = {"is_completed": 0} if pending_only else {}
    cursor = get_db().projects.find(query).sort("created_at", -1)
    df = pd.DataFrame(list(cursor))
    if df.empty: return pd.DataFrame()
    df['id'] = df['_id'].astype(str)
    return df

def update_project_status(pid, is_completed=True):
    val = 1 if is_completed else 0
    res = get_db().projects.update_one({"_id": ObjectId(pid)}, {"$set": {"is_completed": val}})
    return res.modified_count > 0

def delete_project(pid):
    res = get_db().projects.delete_one({"_id": ObjectId(pid)})
    return res.deleted_count > 0
