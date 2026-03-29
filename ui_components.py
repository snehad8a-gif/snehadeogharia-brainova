import streamlit as st
import pandas as pd

def render_edit_habit_form(habit_id, current_data):
    """Render form to edit an existing habit (Interactive, no st.form)."""
    st.subheader(f"Edit Habit: {current_data['name']}")
    
    col_name, col_cat = st.columns([2, 1])
    with col_name:
        name = st.text_input("Name", value=current_data['name'], key=f"edit_name_{habit_id}")
    with col_cat:
        category_options = ["Health", "Productivity", "Learning", "Mindfulness", "Other"]
        try:
            cat_index = category_options.index(current_data['category'])
        except:
            cat_index = 0
        category = st.selectbox("Category", category_options, index=cat_index, key=f"edit_cat_{habit_id}")

    col1, col2 = st.columns(2)
    with col1:
        target_value = st.number_input("Daily Target (Times/Mins)", min_value=1, value=current_data.get('target_value', 1), key=f"edit_target_{habit_id}")

    with col2:
        freq_type_options = {
            "daily": "Every Day",
            "days_of_week": "Specific Days of Week",
            "weekly": "Once a Week",
            "biweekly": "Every 2 Weeks",
            "monthly": "Once a Month",
            "bimonthly": "Every 2 Months",
            "custom": "Every X Days"
        }
        # Find index of current freq type
        current_ftype = current_data.get('frequency_type', 'daily')
        if current_ftype not in freq_type_options: current_ftype = 'daily'
        
        ftype_keys = list(freq_type_options.keys())
        ftype_index = ftype_keys.index(current_ftype)
        
        frequency_type = st.selectbox(
            "Frequency", 
            options=ftype_keys, 
            format_func=lambda x: freq_type_options[x],
            index=ftype_index,
            key=f"edit_freq_{habit_id}"
        )
        
        frequency_value = None
        if frequency_type == "days_of_week":
            default_days = current_data.get('frequency_value', '').split(',') if current_data.get('frequency_value') else ["Mon", "Wed", "Fri"]
            default_days = [d for d in default_days if d]
            days = st.multiselect("Select Days", ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], default=default_days, key=f"edit_days_{habit_id}")
            if days:
                frequency_value = ",".join(days)
        
        elif frequency_type in ["weekly", "biweekly"]:
            days_list = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
            curr_val = current_data.get('frequency_value', 'Mon')
            if curr_val not in days_list: curr_val = 'Mon'
            day = st.selectbox(f"Which Day?", days_list, index=days_list.index(curr_val), key=f"edit_day_single_{habit_id}")
            frequency_value = day
            
        elif frequency_type in ["monthly", "bimonthly"]:
            curr_val = int(current_data.get('frequency_value', 1))
            day = st.number_input("Day of Month (1-31)", 1, 31, curr_val, key=f"edit_month_day_{habit_id}")
            frequency_value = str(day)
            
        elif frequency_type == "custom":
            curr_val = int(current_data.get('frequency_value', 3))
            days = st.number_input("Every X Days", 1, 365, curr_val, key=f"edit_custom_days_{habit_id}")
            frequency_value = str(days)

    if st.button("Save Changes 💾", key=f"save_{habit_id}"):
            return {
            "name": name, 
            "category": category, 
            "frequency_type": frequency_type,
            "frequency_value": frequency_value,
            "target_value": target_value
        }
    return None


def render_add_habit_form():
    """Render form to add a new habit (Interactive, no st.form)."""
    st.subheader("New Habit Goal")
    name = st.text_input("What habit do you want to build?", placeholder="e.g., Read Book").strip()
    
    col1, col2 = st.columns(2)
    with col1:
        category = st.selectbox("Category", ["Health", "Productivity", "Learning", "Mindfulness", "Other"])
        target_value = st.number_input("Daily Target (Minutes/Times)", min_value=1, value=1)
        
    with col2:
        freq_type_options = {
            "daily": "Every Day",
            "days_of_week": "Specific Days of Week",
            "weekly": "Once a Week",
            "biweekly": "Every 2 Weeks",
            "monthly": "Once a Month",
            "bimonthly": "Every 2 Months",
            "custom": "Every X Days"
        }
        frequency_type = st.selectbox(
            "Frequency", 
            options=list(freq_type_options.keys()), 
            format_func=lambda x: freq_type_options[x]
        )
        
        frequency_value = None
        if frequency_type == "days_of_week":
            days = st.multiselect("Select Days", ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], default=["Mon", "Wed", "Fri"])
            if days:
                frequency_value = ",".join(days)
        
        elif frequency_type in ["weekly", "biweekly"]:
            day = st.selectbox("Which Day?", ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
            frequency_value = day
        
        elif frequency_type in ["monthly", "bimonthly"]:
            day = st.number_input("Day of Month (1-31)", 1, 31, 1)
            frequency_value = str(day)
        
        elif frequency_type == "custom":
            days = st.number_input("Every X Days", 1, 365, 3)
            frequency_value = str(days)
    
    if st.button("Create Habit 🚀", type="primary"):
        if not name:
            st.error("Please enter a habit name.")
            return None
        
        # Validation for types requiring value
        if frequency_type != "daily" and frequency_type != "custom" and not frequency_value:
             # Custom and Daily might handle logic differently, but custom needs value too.
             # Actually daily is fine without value.
             pass

        if frequency_type == "days_of_week" and not frequency_value:
             st.error("Please select at least one day.")
             return None

        return {
            "name": name, 
            "category": category, 
            "frequency_type": frequency_type,
            "frequency_value": frequency_value,
            "target_value": target_value
        }
    return None


def render_habit_card(habit, logs, on_complete):
    """
    Renders a card for a single habit using native Streamlit colored containers (Alerts).
    """
    today = pd.Timestamp.now().strftime("%Y-%m-%d")
    is_done = False
    # Check if habit is done for today
    if not logs.empty:
        if not logs[
            (logs['habit_id'] == habit['id']) & 
            (logs['date'] == today)
        ].empty:
            is_done = True
            
    # Layout: Bordered Container (Targeted by CSS :has for color)
    with st.container(border=True):
        c1, c2 = st.columns([6, 1])
        
        with c1:
            st.markdown(f"#### {habit['name']}")
            # Use emoji mapping for visual flair
            cat_emoji = {
                "Health": "💪", "Productivity": "⚡", "Learning": "📚", 
                "Mindfulness": "🧘", "Other": "✨"
            }.get(habit['category'], "✨")
            
            # The word 'Health', 'Productivity' etc must be present for CSS regex
            st.caption(f"{cat_emoji} {habit['category']}  •  📅 {format_frequency(habit)}  •  🎯 {habit['target_value']}")
            
        with c2:
            st.write("") # Spacer
            if is_done:
                st.button("✅", key=f"btn_done_{habit['id']}", disabled=True)
            else:
                if st.button("Done", key=f"btn_{habit['id']}", help="Mark as Done"):
                    # on_complete is log_habit_completion (returns success, reward_dict)
                    success, reward = on_complete(habit['id'], today)
                    if success:
                        st.session_state.latest_reward = reward
                        st.rerun()

def get_category_color(category):
    colors = {
        "Health": "#00C853",
        "Productivity": "#2962FF",
        "Learning": "#FFD600",
        "Mindfulness": "#AA00FF",
        "Other": "#9E9E9E"
    }
    return colors.get(category, "#9E9E9E")

def format_frequency(habit):
    """Helper to display frequency nicely."""
    ftype = habit['frequency_type']
    val = habit['frequency_value']
    
    if ftype == 'daily':
        return "Every Day"
    elif ftype == 'days_of_week':
        return f"On {val}"
    elif ftype == 'weekly':
        return f"Weekly on {val}"
    elif ftype == 'biweekly':
        return f"Every 2 Weeks on {val}"
    elif ftype == 'monthly':
        return f"Monthly on Day {val}"
    elif ftype == 'bimonthly':
        return f"Every 2 Months on Day {val}"
    elif ftype == 'custom':
        return f"Every {val} Days"
    return ftype
