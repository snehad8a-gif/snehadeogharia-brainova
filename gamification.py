import json

# --- CONFIGURATION ---
XP_PER_COMPLETION = 10
XP_STREAK_BONUS_7 = 50
XP_STREAK_BONUS_30 = 200

LEVELS = [
    {"level": 1, "name": "🌱 Beginner", "xp_required": 0},
    {"level": 2, "name": "🧱 Builder", "xp_required": 100},
    {"level": 3, "name": "🏃 Striver", "xp_required": 300},
    {"level": 4, "name": "🛡️ Guardian", "xp_required": 600},
    {"level": 5, "name": "⚔️ Warrior", "xp_required": 1000},
    {"level": 6, "name": "🧘 Master", "xp_required": 1500},
    {"level": 7, "name": "👑 Legend", "xp_required": 2500},
]

BADGES = {
    "first_step": {"name": "First Step", "icon": "👟", "desc": "Complete your first habit"},
    "hat_trick": {"name": "Hat Trick", "icon": "🎩", "desc": "Complete 3 habits in one day"},
    "week_warrior": {"name": "Week Warrior", "icon": "🔥", "desc": "Achieve a 7-day streak"},
    "month_master": {"name": "Monthly Master", "icon": "🏆", "desc": "Achieve a 30-day streak"},
}

# --- PURE LOGIC ---

def get_level_info(total_xp):
    """Return the current level object based on total XP."""
    current = LEVELS[0]
    for lvl in LEVELS:
        if total_xp >= lvl["xp_required"]:
            current = lvl
        else:
            break
    
    # Find next level
    next_level = None
    for lvl in LEVELS:
        if lvl["xp_required"] > current["xp_required"]:
            next_level = lvl
            break
            
    return current, next_level

def calculate_xp_gain(streak_current, streak_before):
    """
    Calculate XP earned for a completion.
    """
    xp = XP_PER_COMPLETION
    
    # Check for bonuses based on hitting milestones NOW
    # If streak was 6 and now is 7, we hit 7.
    if streak_current == 7 and streak_before < 7:
        xp += XP_STREAK_BONUS_7
        
    if streak_current == 30 and streak_before < 30:
        xp += XP_STREAK_BONUS_30
        
    return xp

def check_new_badges(logs_df, habits_df, current_badges):
    """
    Check if any new badges are unlocked.
    logs_df: All logs
    current_badges: list of badge_ids already unlocked
    """
    new_unlocked = []
    
    # 1. First Step
    if "first_step" not in current_badges and not logs_df.empty:
        new_unlocked.append("first_step")
        
    # 2. Hat Trick (3 in one day)
    # We need to check if TODAY has >= 3 completions? 
    # Usually passed logs include the latest one.
    if "hat_trick" not in current_badges and not logs_df.empty:
        today_str = logs_df.iloc[0]['date'] # Assuming sorted DESC
        today_logs = logs_df[logs_df['date'] == today_str]
        if len(today_logs) >= 3:
            new_unlocked.append("hat_trick")
            
    # Streak badges refer to specific habits, so this function is general.
    # Individual habit badges are better checked at the time of completion using the streak value.
    
    return new_unlocked
