import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import timedelta
from src.utils import is_habit_due

def calculate_streaks(habit, habit_logs):
    """
    Calculate current streak based on 'Consecutive Due Dates Completed'.
    """
    if habit_logs.empty:
        return 0
    
    today = pd.Timestamp.now().date()
    try:
        created_at = pd.to_datetime(habit['created_at']).date()
    except:
        return 0
        
    if created_at > today: return 0

    # Get all dates where habit was due, up to today
    due_dates = []
    curr = created_at
    while curr <= today:
        if is_habit_due(habit, curr):
            due_dates.append(curr)
        curr += timedelta(days=1)
        
    if not due_dates: return 0
    
    due_dates.sort(reverse=True)
    logged_dates = set(pd.to_datetime(habit_logs['date']).dt.date)
    
    streak = 0
    for d in due_dates:
        if d in logged_dates:
            streak += 1
        else:
            if d == today:
                continue
            else:
                break
    return streak

def calculate_completion_rate(habit, habit_logs):
    """
    Calculate completion percentage: (Days Completed / Days Due) * 100
    """
    today = pd.Timestamp.now().date()
    try:
        created_at = pd.to_datetime(habit['created_at']).date()
    except:
        return 0.0, 0
    
    if created_at > today: return 0.0, 0
    
    total_due = 0
    curr = created_at
    while curr <= today:
        if is_habit_due(habit, curr):
            total_due += 1
        curr += timedelta(days=1)
        
    completed_count = len(habit_logs['date'].unique()) 
    
    if total_due == 0: return 0.0, 0
    pct = min(100.0, (completed_count / total_due) * 100)
    return pct, total_due

def calculate_missed_habits(habits, logs, days=30):
    """
    Identify habits missed most frequently in the last X days.
    """
    today = pd.Timestamp.now().date()
    start_date = today - timedelta(days=days)
    
    missed_data = []
    
    for _, habit in habits.iterrows():
        missed_count = 0
        total_due = 0
        
        # Determine habit start (cannot miss before created)
        try:
            h_created = pd.to_datetime(habit['created_at']).date()
        except:
            h_created = start_date
            
        check_start = max(start_date, h_created)
        
        # Iterate days
        curr = check_start
        habit_logs = logs[logs['habit_id'] == habit['id']]
        logged_dates = set(pd.to_datetime(habit_logs['date']).dt.date) if not habit_logs.empty else set()
        
        while curr < today: # Don't count today as missed yet
            if is_habit_due(habit, curr):
                total_due += 1
                if curr not in logged_dates:
                    missed_count += 1
            curr += timedelta(days=1)
            
        if missed_count > 0:
            missed_data.append({
                "Habit": habit['name'],
                "Missed": missed_count,
                "Total Due": total_due,
                "Miss Rate": (missed_count/total_due*100) if total_due > 0 else 0
            })
            
    df = pd.DataFrame(missed_data)
    if "Missed" in df.columns:
        return df.sort_values("Missed", ascending=False)
    return df

def get_day_of_week_stats(logs):
    """
    Return total completions by day of week (Mon=0, Sun=6).
    """
    if logs.empty:
        return pd.DataFrame()
        
    df = logs.copy()
    df['date'] = pd.to_datetime(df['date'])
    df['day_name'] = df['date'].dt.day_name()
    # Ensure correct order
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    stats = df['day_name'].value_counts().reindex(days_order, fill_value=0).reset_index()
    stats.columns = ['Day', 'Completions']
    return stats

def render_analytics(habits, logs):
    if habits.empty:
        st.info("No data yet. Start tracking habits!")
        return

    st.subheader("📊 Analytics Dashboard")
    
    # --- GLOBAL METRICS ---
    total_logs = len(logs)
    active_habits = len(habits)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Active Habits", active_habits)
    m2.metric("Total Check-ins", total_logs)
    
    # Calculate per-habit metrics for table
    metrics = []
    for _, habit in habits.iterrows():
        habit_logs = logs[logs['habit_id'] == habit['id']]
        streak = calculate_streaks(habit, habit_logs)
        rate, _ = calculate_completion_rate(habit, habit_logs)
        metrics.append({
            "Name": habit['name'],
            "Streak": streak,
            "Completion Rate": rate
        })
    df_metrics = pd.DataFrame(metrics)
    
    avg_rate = df_metrics['Completion Rate'].mean() if not df_metrics.empty else 0
    m3.metric("Avg Completion Rate", f"{avg_rate:.1f}%")
    
    st.divider()

    # --- 1. TOP STRUGGLES ---
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.markdown("### ⚠️ Top Struggles (Last 30 Days)")
        st.caption("Habits you missed the most recently.")
        missed_df = calculate_missed_habits(habits, logs)
        
        if not missed_df.empty:
            st.dataframe(
                missed_df[['Habit', 'Missed', 'Miss Rate']].style.format({"Miss Rate": "{:.1f}%"}),
                use_container_width=True,
                hide_index=True
            )
        else:
            st.success("🎉 No missed habits in the last 30 days! Perfect record!")

    # --- 2. WEEKLY RHYTHM ---
    with c2:
        st.markdown("### 📅 Weekly Rhythm")
        st.caption("Which days are you most consistent?")
        day_stats = get_day_of_week_stats(logs)
        
        if not day_stats.empty:
            fig = px.bar(day_stats, x='Day', y='Completions', 
                         color='Completions', color_continuous_scale='Viridis')
            fig.update_layout(xaxis_title=None, yaxis_title=None, showlegend=False, height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough data to show weekly rhythm.")

    st.divider()

    # --- 3. HABIT PERFORMANCE TABLE ---
    st.markdown("### 🏆 Habit Leaderboard")
    if not df_metrics.empty:
        st.dataframe(
            df_metrics.sort_values("Completion Rate", ascending=False).style.format({"Completion Rate": "{:.1f}%"}),
            use_container_width=True,
            hide_index=True
        )
