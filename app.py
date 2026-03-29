import streamlit as st
import pandas as pd
import datetime
from src.database import init_db
from src.data_manager import (
    add_project, get_projects, load_habits, load_logs, add_habit, log_habit_completion, delete_habit, edit_habit,
    add_reminder, get_reminders, update_project_status, update_reminder_status, delete_reminder
)
from src.ui_components import render_add_habit_form, render_habit_card, render_edit_habit_form
from src.analytics import render_analytics
from src.ml_logic import get_motivational_message, get_smart_suggestions
from src.utils import is_habit_due
from src.auth import check_password

st.set_page_config(
    page_title="Smart Habit Tracker",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Authentication Gate
if not check_password():
    st.stop()

st.title("✨ Smart Habit Tracker")

# DB Initialization
if "db_initialized" not in st.session_state:
    if init_db():
        st.session_state.db_initialized = True
    else:
        st.error("Failed to initialize database.")
        st.stop()

# Navigation
selected_tab = st.radio(
    "Navigation", 
    ["🔥 Dashboard", "➕ Add Habit", "📝 Add Reminder", "🗂️ Add Project", "📊 Analytics", "⚙️ Settings"], 
    horizontal=True,
    label_visibility="collapsed"
)

# Custom Navbar CSS
st.markdown("""
<style>
    div[role="radiogroup"] {
        display: flex;
        flex-wrap: wrap; 
        justify-content: center;
        gap: 10px;
        background-color: #0E1117;
        padding: 10px;
        margin-bottom: 20px;
        border-bottom: 1px solid #262730;
    }
    div[role="radiogroup"] label {
        background-color: #262730;
        padding: 12px 20px;
        border-radius: 15px;
        border: 1px solid #363945;
        cursor: pointer;
        transition: all 0.2s;
        font-weight: 600;
        margin: 5px !important; 
        flex-grow: 1; 
        text-align: center;
        min-width: 140px;
    }
    div[data-testid="stRadio"] label:hover {
        background-color: #363945;
    }
    div[role="radiogroup"] > label[data-checked="true"] {
        background: linear-gradient(90deg, #F63366 0%, #FF6B6B 100%);
        color: white !important;
        border: none;
    }
</style>
""", unsafe_allow_html=True)

from src.gamification import get_level_info

if selected_tab == "🔥 Dashboard":
    # --- GAMIFICATION HEADER ---
    from src.data_manager import get_user_progress
    user_progress = get_user_progress()
    curr_lvl, next_lvl = get_level_info(user_progress['total_xp'])
    
    # Calculate Progress %
    if next_lvl:
        needed = next_lvl['xp_required'] - curr_lvl['xp_required']
        current = user_progress['total_xp'] - curr_lvl['xp_required']
        # clamp between 0 and 1
        progress_val = min(1.0, max(0.0, current / needed)) if needed > 0 else 1.0
        str_progress = f"{user_progress['total_xp']} / {next_lvl['xp_required']} XP"
    else:
        progress_val = 1.0
        str_progress = "Max Level Reached!"

    with st.container(border=True):
        c1, c2 = st.columns([1, 4])
        with c1:
            st.metric("Level", f"{curr_lvl['level']}", curr_lvl['name'])
        with c2:
            st.write(f"**XP Progress** ({str_progress})")
            st.progress(progress_val)
    
    st.divider()

    # --- REWARD POPUP SYSTEM ---
    if "latest_reward" in st.session_state:
        reward = st.session_state.latest_reward
        xp = reward.get('xp_earned', 0)
        st.toast(f"Heroic! +{xp} XP 🌟")
        
        if reward.get('level_up'):
            st.balloons()
            lvl = reward['current_level']
            st.success(f"🎉 **LEVEL UP!** You are now a **{lvl['name']}** (Level {lvl['level']})!")
            
        del st.session_state['latest_reward']

    # --- 0. Projects Section ---
    projects = get_projects(pending_only=True)
    if not projects.empty:
        st.markdown("### 🗂️ Pending Projects")
        for idx, row in projects.iterrows():
            # Determine icon for CSS targeting
            icon = "🚨" if row['priority'] == 'high' else "⚠️" if row['priority'] == 'medium' else "🟢"
            
            with st.container(border=True):
                c1, c2 = st.columns([6, 1])
                with c1:
                    # Emoji must be present for :has() selector to work
                    st.markdown(f" <b style='font-size: 1.5rem;'>{icon} {row['text']}</b>", unsafe_allow_html=True)
                with c2:
                    if st.button("Done", key=f"dash_project_{row['id']}", help="Mark Done"):
                        update_project_status(row['id'], True)
                        st.rerun()

    # --- 1. Reminders Section ---
    reminders = get_reminders(pending_only=True)
    if not reminders.empty:
        st.markdown("### 📝 Reminders")
        for idx, row in reminders.iterrows():
            # Determine icon for CSS targeting
            icon = "🚨" if row['priority'] == 'high' else "⚠️" if row['priority'] == 'medium' else "🟢"
            
            with st.container(border=True):
                c1, c2 = st.columns([6, 1])
                with c1:
                    # Emoji must be present for :has() selector to work
                    st.markdown(f" <b style='font-size: 1.5rem;'>{icon} {row['text']}</b>", unsafe_allow_html=True)
                with c2:
                    if st.button("Done", key=f"dash_rem_{row['id']}", help="Mark Done"):
                        update_reminder_status(row['id'], True)
                        st.rerun()

    # --- 2. Habits Section ---
    st.markdown("### Today's Focus")
    
    habits = load_habits(active_only=True)
    logs = load_logs()
    
    if habits.empty:
        st.info("No habits found. Go to 'Add Habit' to start!")
    else:
        # 🧠 Smart Section
        suggestions = get_smart_suggestions(habits, logs)
        if suggestions:
             st.info(suggestions[0])

        # Filter for TODAY
        today = pd.Timestamp.now()
        today_str = today.strftime("%Y-%m-%d")
        
        todays_habits = []
        for _, habit in habits.iterrows():
            if is_habit_due(habit, today):
                todays_habits.append(habit)
        
        todays_habits_df = pd.DataFrame(todays_habits)

        # Filter out Completed (Vanish Effect)
        if not todays_habits_df.empty:
            pending_habits = []
            if logs.empty:
                 pending_habits = todays_habits_df
            else:
                completed_ids = logs[logs['date'].astype(str) == today_str]['habit_id'].unique()
                pending_habits = todays_habits_df[~todays_habits_df['id'].isin(completed_ids)]
            
            if pending_habits.empty:
                 st.balloons()
                 st.success("🎉 All habits completed for today! You are crushing it!")
            else:
                for index, habit in pending_habits.iterrows():
                    render_habit_card(habit, logs, log_habit_completion)
        else:
            st.write("No habits scheduled for today.")

elif selected_tab == "➕ Add Habit":
    st.write("### Create New Habit")
    
    if "habit_success" in st.session_state:
        st.success(st.session_state.habit_success)
        del st.session_state["habit_success"]
        
    habit_data = render_add_habit_form()
    if habit_data:
        if add_habit(habit_data):
            st.session_state.habit_success = f"Habit '{habit_data['name']}' created successfully!"
            st.rerun()
        else:
            st.error("Failed to save habit.")

elif selected_tab == "📝 Add Reminder":
    st.write("### 🧠 Sticky Reminders")
    st.caption("A place for non-habit tasks like 'Call Mom' or 'Pay Bills'")
    
    # Callback for adding reminder safely
    def add_reminder_callback():
        text = st.session_state.get("rem_input", "").strip()
        priority = st.session_state.get("rem_priority", "Medium")
        
        if text:
            if add_reminder(text, priority.lower()):
                st.toast("Reminder added successfully! 🚀")
                st.session_state.rem_input = "" # Clear input safely
            else:
                st.error("Failed to add reminder.")
        # No else needed, empty input does nothing

    if "rem_input" not in st.session_state: st.session_state.rem_input = ""
    
    st.text_input("New Reminder", label_visibility="collapsed", placeholder="What needs to be done?", key="rem_input")

    c1, c2 = st.columns([3, 1],gap="large")
    with c1:
        st.selectbox("Priority", ["High", "Medium", "Low"], label_visibility="collapsed", index=1, key="rem_priority")
    with c2:
        st.button("Add Reminder", on_click=add_reminder_callback)

    st.divider()
    
    # List Reminders
    reminders = get_reminders(pending_only=True)
    if reminders.empty:
        st.info("No active reminders. You're free! 🎉")
    else:
        st.subheader("⚠️ Pending Reminders")
        for idx, row in reminders.iterrows():
            # Determine icon for CSS targeting
            icon = "🚨" if row['priority'] == 'high' else "⚠️" if row['priority'] == 'medium' else "🟢"
            
            # Layout: Box with colored background via CSS
            with st.container(border=True):
                c1, c2 = st.columns([6, 1])
                with c1:
                    # Emoji must be present for :has() selector to work
                    st.markdown(f"**{icon} {row['text']}**")
                with c2:
                    if st.button("Done", key=f"dash_rem_{row['id']}", help="Mark Done"):
                        update_reminder_status(row['id'], True)
                        st.rerun()
        st.divider()

elif selected_tab == "🗂️ Add Project":
    st.write("### 🗂️ Add Projects")
    st.caption("A place to track larger tasks (projects) or goals.")
    
    def add_project_callback():
        title = st.session_state.get("proj_title", "").strip()
        desc = st.session_state.get("proj_desc", "").strip()
        priority = st.session_state.get("proj_priority", "Medium")
        
        if title:
            if add_project(title, desc, priority.lower()):
                st.toast("Project added successfully! 🚀")
                st.session_state.proj_title = ""
                st.session_state.proj_desc = ""
            else:
                st.error("Failed to add project.")
        else:
            st.warning("Project title is required.")

    if "proj_title" not in st.session_state: st.session_state.proj_title = ""
    if "proj_desc" not in st.session_state: st.session_state.proj_desc = ""

    st.text_input("On which project do you wish to work?", placeholder="e.g. smart habit tracker", key="proj_title")
    
    c1, c2 = st.columns([3,2])
    with c1:
        st.text_input("Description", placeholder="Add a brief description (optional)", key="proj_desc")
    with c2:
        st.selectbox("Priority", ["High", "Medium", "Low"], index=1, key="proj_priority")

    st.button("Add Project", on_click=add_project_callback)
        
    st.divider()
    
    # List Projects
    projects = get_projects(pending_only=True)
    if projects.empty:
        st.info("No active Projects. You're free! 🎉")
    else:
        st.subheader("⚠️ Pending Projects")
        for idx, row in projects.iterrows():
            # Determine icon for CSS
            p_emoji = "🟥" if row['priority'] == 'high' else "🟨" if row['priority'] == 'medium' else "🟩"
            
            with st.container(border=True):
                rc1, rc2 = st.columns([6, 1])
                
                with rc1:
                    st.markdown(f"**{p_emoji} {row['text']}**")
                    if row['description']:
                        st.caption(row['description'])
                with rc2:
                    if st.button("Done", key=f"project_done_{row['id']}", help="Mark as Done"):
                        update_project_status(row['id'], True)
                        st.rerun()
            st.divider()

elif selected_tab == "📊 Analytics":
    habits = load_habits()
    logs = load_logs()
    render_analytics(habits, logs)

elif selected_tab == "⚙️ Settings":
    st.header("⚙️ Habit Management Center")
    st.caption("Manage your data, clear old tasks, and organize your workspace.")
    
    # 3 Sub-tabs for content
    tab_habits, tab_reminders, tab_projects = st.tabs(["✨ Habits", "📝 Reminders", "🗂️ Projects"])
    
    # --- HABITS MANAGEMENT ---
    with tab_habits:
        habits = load_habits()
        if "edit_mode_id" not in st.session_state:
            st.session_state.edit_mode_id = None

        if habits.empty:
            st.info("No habits to manage yet.")
        else:
            # Edit Mode Logic
            if st.session_state.edit_mode_id:
                habit_to_edit = habits[habits['id'] == st.session_state.edit_mode_id].iloc[0]
                
                if st.button("← Back to List", key="back_edit"):
                    st.session_state.edit_mode_id = None
                    st.rerun()
                    
                from src.ui_components import render_edit_habit_form
                updated_data = render_edit_habit_form(habit_to_edit['id'], habit_to_edit)
                
                if updated_data:
                    if edit_habit(habit_to_edit['id'], updated_data):
                        st.success("Habit updated successfully!")
                        st.session_state.edit_mode_id = None
                        st.rerun()
                    else:
                        st.error("Failed to update habit.")
            else:
                # List Mode
                for index, habit in habits.iterrows():
                    with st.container(border=True):
                        c1, c2 = st.columns([4, 1])
                        with c1:
                            st.markdown(f"**{habit['name']}**")
                            st.caption(f"{habit['category']} • {habit['frequency_type']}")
                        with c2:
                            # Use smaller columns for buttons
                            b1, b2 = st.columns(2)
                            with b1:
                                if st.button("✏️", key=f"edit_{habit['id']}", help="Edit Habit"):
                                    st.session_state.edit_mode_id = habit['id']
                                    st.rerun()
                            with b2:
                                if st.button("🗑️", key=f"del_{habit['id']}", help="Delete Habit"):
                                    if delete_habit(habit['id']):
                                        st.success("Deleted!")
                                        st.rerun()

    # --- REMINDERS MANAGEMENT ---
    with tab_reminders:
        # Get ALL reminders (active + completed) to allow cleanup
        reminders = get_reminders(pending_only=False)
        if reminders.empty:
            st.info("No reminders found.")
        else:
            for index, row in reminders.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        # Status Icon
                        is_done = row['is_completed'] == 1
                        status = "✅" if is_done else "⏳"
                        priority_icon = "🚨" if row['priority'] == 'high' else "⚠️" if row['priority'] == 'medium' else "🟢"
                        
                        st.markdown(f"**{priority_icon} {row['text']}**")
                        st.caption(f"Status: {status} • {'Completed' if is_done else 'Pending'}")
                        
                    with c2:
                        st.write("") # Align
                        if st.button("🗑️", key=f"del_rem_{row['id']}", help="Delete Reminder"):
                            if delete_reminder(row['id']):
                                st.rerun()

    # --- PROJECTS MANAGEMENT ---
    with tab_projects:
        from src.data_manager import delete_project
        projects = get_projects(pending_only=False)
        if projects.empty:
            st.info("No projects found.")
        else:
            for index, row in projects.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([5, 1])
                    with c1:
                        is_done = row['is_completed'] == 1
                        status = "✅" if is_done else "⏳"
                        p_emoji = "🟥" if row['priority'] == 'high' else "🟨" if row['priority'] == 'medium' else "🟩"
                        
                        st.markdown(f"**{p_emoji} {row['text']}**")
                        if row['description']:
                            st.caption(row['description'])
                        st.caption(f"Status: {status}")
                        
                    with c2:
                        st.write("")
                        if st.button("🗑️", key=f"del_proj_{row['id']}", help="Delete Project"):
                            if delete_project(row['id']):
                                st.rerun()
