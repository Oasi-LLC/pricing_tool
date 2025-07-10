# Calendar View Implementation Plan

## Overview
This document outlines the plan for implementing a calendar view in the pricing tool, complementing the existing table view. The calendar view will provide a more intuitive way to manage rates, view booking patterns, and handle Length of Stay (LOS) adjustments.

## 1. Current System Analysis

### 1.1 Table View Flow
- **Initial Setup**
  - Property/unit pool selection
  - Date range selection
  - Optional column display settings
  - Rate generation trigger

- **Data Display**
  - Tabular format showing date/listing combinations
  - Core columns: Select, View Details, Date, Property, Tier, Day of Week, Occupancy %, Live Rate, Suggested Rate, Delta, Editable Rate, Flag, Status
  - Optional columns: Historical Occupancy %, Pace

- **Interaction Capabilities**
  - Multi-level filtering
  - Bulk selection and actions
  - Individual rate editing
  - Detailed view access
  - Booking status visualization

### 1.2 Current Rate Management
- Individual rate adjustments
- Bulk rate updates
- Delta monitoring
- Booking status tracking
- Flag system for special conditions

## 2. Calendar View Design

### 2.1 User Interface Components

#### 2.1.1 Main Calendar Layout
```
[Property Selector] [Date Range] [View Toggle]
[Month/Week Toggle] [Color Legend] [LOS Display Toggle]

[Calendar Grid]
Mon  Tue  Wed  Thu  Fri  Sat  Sun
[1]  [2]  [3]  [4]  [5]  [6]  [7]
[8]  [9]  [10] [11] [12] [13] [14]
...
```

#### 2.1.2 Day Cell Structure
```
[Date]
[Property Name]
[Rate] [Booking Status]
[LOS Indicator]
```

#### 2.1.3 Expanded Day View
```
[Date] [Property]
-------------------------
Current Rate: $XXX
Suggested Rate: $XXX
Delta: $XXX

Booking Status: [Booked/Available]
LOS: [Current LOS]

[Edit Rate] [Adjust LOS]
```

### 2.2 Visual Indicators

#### 2.2.1 Color Coding
- Booking Status
  - Booked: Red
  - Available: Green
  - Partially Booked: Yellow
- Rate Status
  - Above Suggested: Blue
  - Below Suggested: Orange
  - At Suggested: Green
- LOS Status
  - Short Stay: Light Blue
  - Long Stay: Dark Blue
- Special Dates
  - Events: Purple
  - Holidays: Red

#### 2.2.2 Icons
- Booking: 🔒
- Rate Status: ↑/↓
- LOS: 📅
- Flags: ⚠️

## 3. Functionality Implementation

### 3.1 Core Features

#### 3.1.1 View Toggle
```python
view_mode = st.radio(
    "Select View Mode:",
    ["Table View", "Calendar View"],
    horizontal=True
)
```

#### 3.1.2 Calendar Navigation
- Month navigation
- Week view option
- Quick date jump
- Property switching

#### 3.1.3 Selection Methods
- Single day click
- Date range selection (click and drag)
- Non-contiguous selection (Shift+click)
- Property-based selection

### 3.2 Rate Management

#### 3.2.1 Single Day Operations
- Rate editing
- LOS adjustment
- Booking status update
- Flag management

#### 3.2.2 Multi-day Operations
- Bulk rate updates
- LOS pattern application
- Booking status changes
- Flag application

### 3.3 Data Synchronization

#### 3.3.1 Real-time Updates
- Rate changes
- Booking status
- LOS modifications
- Flag updates

#### 3.3.2 View Synchronization
- Table view updates
- Calendar view updates
- Filter synchronization
- Selection state maintenance

## 4. Technical Implementation

### 4.1 New Components

#### 4.1.1 Calendar Component
```python
def render_calendar_view(df, property_config):
    calendar = st.container()
    with calendar:
        selected_month = st.date_input("Select Month", datetime.date.today())
        for week in get_weeks_in_month(selected_month):
            cols = st.columns(7)
            for day, col in zip(week, cols):
                with col:
                    render_calendar_day(day, df, property_config)
```

#### 4.1.2 Day Cell Component
```python
def render_calendar_day(day, df, property_config):
    day_data = get_day_data(day, df)
    if st.button(f"{day.day}", key=f"day_{day}"):
        show_rate_editor(day_data)
    if is_booked(day_data):
        st.markdown("🔒")
    st.markdown(f"${day_data['rate']}")
```

#### 4.1.3 Rate Editor Component
```python
def show_rate_editor(day_data):
    with st.form("rate_editor"):
        new_rate = st.number_input("Rate", value=day_data['rate'])
        los = st.number_input("Length of Stay", value=day_data['los'])
        if st.form_submit_button("Update"):
            update_rates(day_data['date'], new_rate, los)
```

### 4.2 Data Structures

#### 4.2.1 Calendar Data Model
```python
calendar_data = {
    'date': datetime.date,
    'listing_id': str,
    'rate': float,
    'booking_status': str,
    'los': int,
    'adjacent_bookings': list
}
```

#### 4.2.2 View State Management
```python
class CalendarViewState:
    selected_dates: list
    selected_properties: list
    current_view: str  # 'month' or 'week'
    color_scheme: dict
    los_display: bool
```

## 5. Integration Points

### 5.1 Existing System Integration
- Property configuration
- Rate calculation engine
- Booking status system
- LOS management
- Flag system

### 5.2 New Integration Points
- Calendar view state management
- View synchronization
- Bulk operation handling
- Export/import functionality

## 6. Implementation Phases

### Phase 1: Basic Calendar View
- Basic calendar grid
- Day cell rendering
- Simple rate display
- Basic navigation

### Phase 2: Interactive Features
- Rate editing
- LOS adjustment
- Booking status display
- Basic filtering

### Phase 3: Advanced Features
- Bulk operations
- Advanced filtering
- Export/import
- View synchronization

### Phase 4: Polish & Optimization
- Performance optimization
- UI/UX improvements
- Bug fixes
- Documentation

## 7. Testing Plan

### 7.1 Unit Tests
- Calendar rendering
- Day cell functionality
- Rate editing
- LOS adjustment

### 7.2 Integration Tests
- View synchronization
- Data consistency
- Bulk operations
- Export/import

### 7.3 User Acceptance Testing
- Usability testing
- Performance testing
- Edge case handling
- Error handling

## 8. Documentation Requirements

### 8.1 Technical Documentation
- Component architecture
- Data flow
- State management
- Integration points

### 8.2 User Documentation
- View switching
- Rate management
- LOS adjustment
- Bulk operations

## 9. Future Enhancements

### 9.1 Potential Features
- Drag-and-drop rate adjustment
- Advanced LOS patterns
- Custom color schemes
- Additional export formats

### 9.2 Performance Optimizations
- Lazy loading
- Caching strategies
- View optimization
- Data structure improvements 