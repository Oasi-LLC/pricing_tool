# Add LOS (Length of Stay) Adjustment Feature

## Overview
Add minimum stay adjustment capability to existing rate push tool, using same push mechanism.

## Implementation Plan

### Step 1: Add LOS Adjustment UI
- Add "Adjust LOS" button next to existing "Adjust Selected" button
- Add session state:
```python
st.session_state.show_los_adjust_modal = False
st.session_state.los_adjustment_amount = 1
```

### Step 2: Add LOS Modal
- Copy existing price adjustment modal pattern:
  - Title: "Adjust Min Stay"
  - Number input: whole numbers only, min=1
  - Increase/Decrease radio buttons
  - Preview using existing COL_EDITABLE_MIN_STAY column
  - Apply/Cancel buttons

### Step 3: Push Integration
- Use existing push mechanism (already handles min_stay)
- Test workflow:
  1. Select rows
  2. Adjust min stay up/down
  3. Preview changes
  4. Push using existing button

## Testing
- Verify min stay ≥ 1 constraint
- Test batch adjustments
- Verify changes in push preview
- Test successful push with LOS changes 