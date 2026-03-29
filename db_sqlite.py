import streamlit as st
import pandas as pd
from datetime import datetime
import json
from src.database import run_query, init_db
from src.gamification import calculate_xp_gain, get_level_info, BADGES

# --- GAMIFICATION DB ---
def init_gamification_db():
    """Ensure user_progress table exists with correct schema."""
    # 1. Create table with minimal schema if it doesn't exist
    query = """
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY,
            total_xp INTEGER DEFAULT 0
        )
    """
    run_query(query)
    
    # 2. Check schema using PRAGMA (Robust Migration)
    res = run_query("PRAGMA table_info(user_progress)")
    existing_columns = [row['name'] for row in res] if res else []
    
    if "unlocked_badges" not in existing_columns:
        try:
            run_query("ALTER TABLE user_progress ADD COLUMN unlocked_badges TEXT DEFAULT '[]'")
        except Exception as e:
            st.error(f"Migration failed: {e}")

    # 3. Ensure raw row exists
    check = run_query("SELECT id FROM user_progress WHERE id = 1")
    if not check:
        # Safe insert now that column exists
        run_query("INSERT INTO user_progress (id, total_xp, unlocked_badges) VALUES (1, 0, '[]')")

# Initialize DBs
init_db()
init_gamification_db()

def get_user_progress():
    """Fetch current user progress."""
    res = run_query("SELECT total_xp, unlocked_badges FROM user_progress WHERE id = 1")
    if res:
        xp, badges_json = res[0]
        return {"total_xp": xp, "unlocked_badges": json.loads(badges_json)}
    return {"total_xp": 0, "unlocked_badges": []}

def update_user_progress(xp_delta, new_badges=None):
    """Add XP and save new badges."""
    curr = get_user_progress()
    new_xp = curr['total_xp'] + xp_delta
    badges = curr['unlocked_badges']
    
    if new_badges:
        for b in new_badges:
            if b not in badges:
                badges.append(b)
    
    run_query(
        "UPDATE user_progress SET total_xp = ?, unlocked_badges = ? WHERE id = 1",
        (new_xp, json.dumps(badges))
    )
    return new_xp, badges

# --- HABITS ---

def load_habits(active_only=True):
    """Load all habits from SQLite."""
    query = "SELECT * FROM habits"
    if active_only:
        query += " WHERE is_active = 1"
    query += " ORDER BY created_at DESC"
    
    df = run_query(query, return_df=True)
    if df.empty:
        # Return empty df with expected columns
        return pd.DataFrame(columns=['id', 'name', 'category', 'frequency_type', 'frequency_value', 'target_value', 'target_unit', 'created_at', 'is_active'])
    return df

def load_logs(days_back=30):
    """Load logs for recent history."""
    # Limit to recent logs for performance, unless needed otherwise
    query = f"""
        SELECT * FROM logs 
        WHERE date >= date('now', '-{days_back} days')
        ORDER BY date DESC
    """
    df = run_query(query, return_df=True)
    if df.empty:
        return pd.DataFrame(columns=['id', 'habit_id', 'date', 'value', 'status', 'notes', 'timestamp'])
    return df

def add_habit(habit_data):
    """Add a new habit to the database."""
    query = """
        INSERT INTO habits (name, category, frequency_type, frequency_value, target_value)
        VALUES (?, ?, ?, ?, ?)
    """
    params = (
        habit_data['name'], 
        habit_data['category'], 
        habit_data['frequency_type'], 
        habit_data['frequency_value'],
        habit_data.get('target_value', 1)
    )
    
    try:
        run_query(query, params)
        # Clear cache logic if we were using st.cache_data, but with SQL we just requery
        return True
    except Exception as e:
        st.error(f"Error adding habit: {e}")
        return False

def edit_habit(habit_id, updated_data):
    """Update an existing habit."""
    query = """
        UPDATE habits 
        SET name = ?, category = ?, frequency_type = ?, frequency_value = ?, target_value = ?
        WHERE id = ?
    """
    params = (
        updated_data['name'],
        updated_data['category'],
        updated_data['frequency_type'],
        updated_data['frequency_value'],
        updated_data['target_value'],
        habit_id
    )
    try:
        run_query(query, params)
        return True
    except Exception as e:
        st.error(f"Error updating habit: {e}")
        return False

def delete_habit(habit_id):
    """Soft delete a habit."""
    query = "UPDATE habits SET is_active = 0 WHERE id = ?"
    try:
        run_query(query, (habit_id,))
        return True
    except Exception as e:
        st.error(f"Error deleting habit: {e}")
        return False

def log_habit_completion(habit_id, date, status="Completed", notes="", value=1):
    """
    Log a habit completion and process Gamification rewards.
    Returns: (bool, dict) -> (Success, RewardInfo)
    RewardInfo keys: 'xp_earned', 'new_level', 'new_badges'
    """
    
    # Check for existing log for this habit and date
    check_query = "SELECT id FROM logs WHERE habit_id = ? AND date = ?"
    existing = run_query(check_query, (habit_id, str(date)))
    
    if existing:
        return False, {}
        
    query = """
        INSERT INTO logs (habit_id, date, status, notes, value)
        VALUES (?, ?, ?, ?, ?)
    """
    try:
        run_query(query, (habit_id, str(date), status, notes, value))
        
        # --- GAMIFICATION LOGIC ---
        # 1. Calculate Streak (Approximate for speed, or fetch logs)
        # To be accurate, we really need the logs.
        # But we can assume if they logged today, we just need to know the PREVIOUS streak.
        # Let's verify via full calc or just assume +1 for now to keep it snappy?
        # No, user wants rewards for streaks. We need to calculate it.
        # We'll do a quick query for this habit's logs.
        
        # We need the HABIT object to calculate streak (for frequency).
        # Fetch habit
        h_res = run_query("SELECT * FROM habits WHERE id = ?", (habit_id,), return_df=True)
        if not h_res.empty:
            habit = h_res.iloc[0]
            # Fetch all logs for this habit
            l_res = run_query("SELECT * FROM logs WHERE habit_id = ?", (habit_id,), return_df=True)
            
            # Use analytics (imported locally to avoid circular deps)
            from src.analytics import calculate_streaks
            current_streak = calculate_streaks(habit, l_res)
            # Previous streak was current - 1 (since we just logged)
            prev_streak = max(0, current_streak - 1)
            
            xp = calculate_xp_gain(current_streak, prev_streak)
            
            # --- BADGE CHECKS ---
            candidate_badges = []
            curr_progress = get_user_progress()
            existing_badges = curr_progress['unlocked_badges']
            
            # 1. Streak Badges
            if current_streak == 7: candidate_badges.append('week_warrior')
            if current_streak == 30: candidate_badges.append('month_master')
            
            # 2. First Step (If XP is 0, this is the first completion)
            if curr_progress['total_xp'] == 0:
                candidate_badges.append('first_step')
                
            # 3. Hat Trick (3rd completion today)
            # We just inserted the log, so count should include it.
            day_count_res = run_query("SELECT COUNT(*) FROM logs WHERE date = ?", (str(date),))
            if day_count_res and day_count_res[0][0] == 3:
                candidate_badges.append('hat_trick')
                
            # Filter only truly new badges
            new_badges_unlocked = [b for b in candidate_badges if b not in existing_badges]
            
            # Update User
            new_xp_total, _ = update_user_progress(xp, new_badges_unlocked)
            
            # Check Level Up
            curr_lvl, next_lvl = get_level_info(new_xp_total)
            prev_lvl, _ = get_level_info(new_xp_total - xp)
            
            level_up = (curr_lvl['level'] > prev_lvl['level'])
            
            return True, {
                "xp_earned": xp,
                "level_up": level_up,
                "current_level": curr_lvl,
                "new_badges": new_badges_unlocked
            }
            
        return True, {"xp_earned": 0}
        
    except Exception as e:
        st.error(f"Error logging habit: {e}")
        return False, {}

def get_habit_stats(habit_id):
    """Get simple stats for a habit."""
    query = """
        SELECT COUNT(*) as count, MAX(date) as last_log 
        FROM logs 
        WHERE habit_id = ?
    """
    res = run_query(query, (habit_id,))
    if res:
        return res[0]
    return None

# --- Reminder System ---

def add_reminder(text, priority='low'):
    query = "INSERT INTO reminders (text, priority) VALUES (?, ?)"
    try:
        run_query(query, (text, priority))
        return True
    except Exception as e:
        st.error(f"Error adding reminder: {e}")
        return False

def get_reminders(pending_only=True):
    query = "SELECT * FROM reminders"
    if pending_only:
        query += " WHERE is_completed = 0"
    query += " ORDER BY created_at DESC"
    return run_query(query, return_df=True)

def update_reminder_status(reminder_id, is_completed=True):
    # Using 1/0 for boolean in SQLite
    val = 1 if is_completed else 0
    query = "UPDATE reminders SET is_completed = ? WHERE id = ?"
    try:
        run_query(query, (val, reminder_id))
        return True
    except:
        return False

def delete_reminder(reminder_id):
    query = "DELETE FROM reminders WHERE id = ?"
    try:
        run_query(query, (reminder_id,))
        return True
    except:
        return False
    
# --- Project Reminder System ---

def add_project(text, description, priority='low'):
    query = "INSERT INTO projects (text, description, priority) VALUES (?, ?, ?)"
    try:
        run_query(query, (text, description, priority))
        return True
    except Exception as e:
        st.error(f"Error adding project: {e}")
        return False

def get_projects(pending_only=True):
    query = "SELECT * FROM projects"
    if pending_only:
        query += " WHERE is_completed = 0"
    query += " ORDER BY created_at DESC"
    return run_query(query, return_df=True)

def update_project_status(project_id, is_completed=True):
    # Using 1/0 for boolean in SQLite
    val = 1 if is_completed else 0
    query = "UPDATE projects SET is_completed = ? WHERE id = ?"
    try:
        run_query(query, (val, project_id))
        return True
    except:
        return False

def delete_project(project_id):
    query = "DELETE FROM projects WHERE id = ?"
    try:
        run_query(query, (project_id,))
        return True
    except:
        return False
