import streamlit as st
import datetime
import pandas as pd
from typing import Dict, List, Optional
import streamlit.components.v1 as components

def get_weeks_in_month(date: datetime.date) -> List[List[datetime.date]]:
    """Get all weeks in the month as a list of lists of dates, with weeks starting on Sunday."""
    # Get the first and last day of the month
    first_day = datetime.date(date.year, date.month, 1)
    if date.month == 12:
        last_day = datetime.date(date.year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        last_day = datetime.date(date.year, date.month + 1, 1) - datetime.timedelta(days=1)

    # Calculate the first Sunday before or on the first day of the month
    days_to_sunday = first_day.weekday() + 1 if first_day.weekday() < 6 else 0
    start_date = first_day - datetime.timedelta(days=days_to_sunday)

    # Calculate the last Saturday after or on the last day of the month
    days_to_saturday = 6 - last_day.weekday() if last_day.weekday() < 6 else 0
    end_date = last_day + datetime.timedelta(days=days_to_saturday)

    # Generate all dates
    current_date = start_date
    weeks = []
    current_week = []

    while current_date <= end_date:
        current_week.append(current_date)
        if len(current_week) == 7:
            weeks.append(current_week)
            current_week = []
        current_date += datetime.timedelta(days=1)

    return weeks

def get_day_data(date: datetime.date, df: pd.DataFrame) -> Dict:
    """Get data for a specific day from the DataFrame."""
    if df is None or df.empty:
        return {
            'rate': 0.0,
            'booking_status': 'unknown',
            'property': 'N/A'
        }
    
    # Filter DataFrame for the specific date
    day_data = df[df['Date'] == date]
    
    if day_data.empty:
        return {
            'rate': 0.0,
            'booking_status': 'unknown',
            'property': 'N/A'
        }
    
    # Get the first row (assuming one property per day for now)
    row = day_data.iloc[0]
    
    return {
        'rate': row.get('Live Rate $', 0.0),
        'booking_status': 'booked' if row.get('Flag') == '🔒 Booked' else 'available',
        'property': row.get('Property', 'N/A')
    }

def render_calendar_view(df: pd.DataFrame, property_config: Dict):
    """Render a true calendar grid as a single HTML table with uniform square cells and improved cell formatting."""
    st.write("### Calendar View")

    today = datetime.date.today()

    # Use correct column names for listings
    property_col = 'Unit Pool' if 'Unit Pool' in df.columns else 'property'
    listing_name_col = 'listing_name' if 'listing_name' in df.columns else 'Listing Name'
    listing_id_col = 'listing_id'

    if df is None or df.empty:
        st.info("No data to display. Please generate rates.")
        return

    # Ensure 'Date' column is datetime.date for comparison
    if not pd.api.types.is_datetime64_any_dtype(df['Date']):
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Date'] = df['Date'].dt.date

    # Only keep future dates (today and onward)
    all_dates = sorted(df['Date'].unique())
    future_dates = [d for d in all_dates if d >= today]
    if not future_dates:
        st.info("No future rates to display.")
        return

    listings = df[[property_col, listing_name_col, listing_id_col]].drop_duplicates().sort_values([property_col, listing_name_col]).reset_index(drop=True)

    # Restore HTML table layout and add JS for direct cell selection
    if 'calendar_selected_cells' not in st.session_state:
        st.session_state['calendar_selected_cells'] = set()

    # Build HTML table with data-cell-id for each cell
    table_html = '''
    <style>
    .calendar-table { border-collapse: collapse; width: 100%; min-width: 900px; }
    .calendar-table th, .calendar-table td { border: 1px solid #444; padding: 0; }
    .calendar-table th { background: #222; color: #fff; font-size: 0.95em; padding: 6px; }
    .calendar-cell {
        width: 90px; height: 70px; min-width: 90px; min-height: 70px;
        text-align: center; vertical-align: middle;
        background: #222; color: #fff; font-size: 1em;
        overflow: hidden; white-space: nowrap;
        display: flex; flex-direction: column; justify-content: center; align-items: center;
        transition: box-shadow 0.2s, border 0.2s, background 0.2s;
        cursor: pointer;
    }
    .calendar-cell.selected {
        border: 3.5px solid #1976d2 !important;
        box-shadow: 0 0 8px 2px #1976d2aa;
        background: #e3f2fd;
        color: #111;
        z-index: 2;
    }
    .calendar-cell.booked {
        background: #1a237e !important;
        color: #fff;
        cursor: not-allowed;
    }
    .occ-dot {
        width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin-top: 2px;
    }
    .occ-verylow { background: #d32f2f; border: 1px solid #8a1c1c; }
    .occ-low { background: #f57c00; border: 1px solid #a04900; }
    .occ-med { background: #fbc02d; border: 1px solid #a6891c; }
    .occ-high { background: #81c784; border: 1px solid #388e3c; }
    .occ-veryhigh { background: #388e3c; border: 1px solid #1b5e20; }
    .calendar-listing { font-weight: 600; background: #181818; color: #fff; min-width: 120px; }
    </style>
    <div style="overflow-x: auto;">
    <table class="calendar-table">
    <thead><tr><th class="calendar-listing">Listing</th>'''
    for day in future_dates:
        day_of_week = day.strftime('%a')
        table_html += f"<th><div style='font-size:0.93em;font-weight:600'>{day_of_week}</div><div>{day.strftime('%b %d')}</div></th>"
    table_html += "</tr></thead><tbody>"

    for _, listing in listings.iterrows():
        table_html += f"<tr><td class='calendar-listing'>{listing[listing_name_col]}</td>"
        for day in future_dates:
            match = df[(df[listing_id_col] == listing[listing_id_col]) & (df['Date'] == day)]
            cell_id = f"{listing[listing_id_col]}_{day}"
            is_selected = cell_id in st.session_state['calendar_selected_cells']
            if not match.empty:
                live_rate = match.iloc[0].get('Live Rate $', 0.0)
                suggested_rate = match.iloc[0].get('Suggested', None)
                flag = match.iloc[0].get('Flag', '')
                los = match.iloc[0].get('Min Stay', '')
                occ = match.iloc[0].get('Occ% (Curr)', None)
                # Compute occupancy dot HTML
                occ_dot = ''
                if occ is not None and not pd.isna(occ):
                    if occ <= 20:
                        occ_dot = "<span class='occ-dot occ-verylow'></span>"
                    elif occ <= 40:
                        occ_dot = "<span class='occ-dot occ-low'></span>"
                    elif occ <= 60:
                        occ_dot = "<span class='occ-dot occ-med'></span>"
                    elif occ <= 80:
                        occ_dot = "<span class='occ-dot occ-high'></span>"
                    else:
                        occ_dot = "<span class='occ-dot occ-veryhigh'></span>"
                cell_classes = 'calendar-cell'
                if flag == "🔒 Booked":
                    cell_classes += ' booked'
                if is_selected and flag != "🔒 Booked":
                    cell_classes += ' selected'
                if flag == "🔒 Booked":
                    cell_content = (
                        f"<div class='{cell_classes}' data-cell-id='{cell_id}' data-booked='true'>"
                        f"<div class='top-line'>${live_rate:.0f}</div>"
                        f"<div class='los'>{los}n</div>"
                        "</div>"
                    )
                else:
                    if suggested_rate is not None and not pd.isna(suggested_rate):
                        top_line = f"${live_rate:.0f} | ${suggested_rate:.0f}"
                    else:
                        top_line = f"${live_rate:.0f}"
                    cell_content = (
                        f"<div class='{cell_classes}' data-cell-id='{cell_id}' data-booked='false'>"
                        f"<div class='top-line'>{top_line}</div>"
                        f"<div class='los'>{los}n</div>"
                        f"{occ_dot}"
                        "</div>"
                    )
            else:
                cell_content = f"<div class='calendar-cell' data-cell-id='{cell_id}' data-booked='false'></div>"
            table_html += f"<td>{cell_content}</td>"
        table_html += "</tr>"
    table_html += "</tbody></table></div>"

    # Inject JS for cell selection
    st.markdown(table_html, unsafe_allow_html=True)
    components.html('''
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('.calendar-cell').forEach(function(cell) {
            cell.addEventListener('click', function() {
                if (cell.getAttribute('data-booked') === 'true') return;
                const cellId = cell.getAttribute('data-cell-id');
                window.parent.postMessage({type: 'streamlit:setComponentValue', key: 'calendar_cell_clicked', value: cellId}, '*');
            });
        });
    });
    </script>
    ''', height=0)

    # Helper for rerun compatible with all Streamlit versions
    def rerun():
        if hasattr(st, 'rerun'):
            st.rerun()
        elif hasattr(st, 'experimental_rerun'):
            st.experimental_rerun()

    # Handle cell click event in Streamlit
    if 'calendar_cell_clicked' in st.session_state:
        cell_id = st.session_state['calendar_cell_clicked']
        if cell_id in st.session_state['calendar_selected_cells']:
            st.session_state['calendar_selected_cells'].remove(cell_id)
        else:
            st.session_state['calendar_selected_cells'].add(cell_id)
        del st.session_state['calendar_cell_clicked']
        rerun()

    # Display selection count
    if st.session_state['calendar_selected_cells']:
        st.write(f"Selected cells: {len(st.session_state['calendar_selected_cells'])}")

    # Add a clear selection button
    if st.button("Clear Selection"):
        st.session_state['calendar_selected_cells'] = set()
        rerun()

    # Add JS to handle cell clicks and update Streamlit state
    st.markdown('''
    <script>
    window.addEventListener('message', (event) => {
        if (event.data && event.data.type === 'calendar_cell_click') {
            const listing_id = event.data.listing_id;
            const date = event.data.date;
            const streamlitEvent = new CustomEvent('streamlit:calendar_cell_click', { detail: { listing_id, date } });
            window.dispatchEvent(streamlitEvent);
        }
    });
    </script>
    ''', unsafe_allow_html=True)

    # Register Streamlit event handler for cell selection
    components.html('''
    <script>
    window.addEventListener('streamlit:calendar_cell_click', function(e) {
        const listing_id = e.detail.listing_id;
        const date = e.detail.date;
        window.parent.postMessage({type: 'streamlit:setComponentValue', key: 'calendar_cell_clicked', value: listing_id + '|' + date}, '*');
    });
    </script>
    ''', height=0)

    # Add selection count badge at the top right of the table
    selection_count = len(st.session_state['calendar_selected_cells'])
    st.markdown(f'''
    <div style="display: flex; justify-content: flex-end; align-items: center; margin-bottom: 0.5em;">
        <span style="background: #1976d2; color: #fff; border-radius: 16px; padding: 0.35em 1.1em; font-weight: 600; font-size: 1.1em;">Selected: {selection_count}</span>
    </div>
    ''', unsafe_allow_html=True) 