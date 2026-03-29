import pandas as pd
import random

def get_motivational_message(streak):
    """Return a message based on streak length."""
    if streak == 0:
        return random.choice([
            "Every journey begins with a single step. Start today!",
            "Don't worry about yesterday. Today is a new opportunity.",
            "Small progress is still progress."
        ])
    elif streak < 3:
        return random.choice([
            "You're off to a great start! Keep it up!",
            "Consistency is key. You're building momentum.",
            "Great job! Two days in a row!"
        ])
    elif streak < 7:
        return random.choice([
            "You're on fire! 🔥",
            "Almost a full week! Don't break the chain!",
            "You are becoming unstoppable."
        ])
    else:
        return random.choice([
            "Legendary streak! 🏆",
            "This habit is now part of you.",
            "Incredible dedication. Use this energy for other goals too!"
        ])

def get_smart_suggestions(habits, logs):
    """
    Analyze logs to find patterns and suggest improvements.
    """
    if logs.empty or habits.empty:
        return ["Start logging your habits to get smart insights!"]
    
    suggestions = []
    
    # Analyze skipped days (simple heuristic)
    # Check if there is a specific day of week where completion is low
    logs['date'] = pd.to_datetime(logs['date'])
    logs['weekday'] = logs['date'].dt.day_name()
    
    weekday_counts = logs['weekday'].value_counts()
    
    if not weekday_counts.empty:
        best_day = weekday_counts.idxmax()
        suggestions.append(f"💡 You happen to be most consistent on **{best_day}s**. Try to schedule your hardest tasks then!")
    
    # Streak check
    for _, habit in habits.iterrows():
        habit_logs = logs[logs['habit_id'] == habit['id']]
        if habit_logs.empty:
            suggestions.append(f"👀 You haven't started **{habit['name']}** yet. How about doing just 5 minutes today?")
    
    if not suggestions:
        suggestions.append("🌟 You are doing great! Keep tracking to unlock more insights.")
        
    return suggestions
