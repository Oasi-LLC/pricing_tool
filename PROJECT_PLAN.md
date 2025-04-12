# Project Plan: Internal Rate Review & Management Tool MVP

## Milestone Summary

| Milestone ID | Milestone Name                       | Key Tasks (Summary)                                                                                                                                                                                                                             | Relevant PRD Sections |
| :----------- | :----------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-------------------- |
| 1            | Setup & Dependencies               | Initialize project structure (`app.py`, `utils/`), `requirements.txt` (Streamlit>=1.22), create backend interface stubs (`utils/backend_interface.py`) with hardcoded data.                                                                        | 3.1, 6, 8, 9.1        |
| 2            | Configuration UI & Generation Trigger | Implement UI for Property/Date selection (`st.multiselect`, `st.date_input`). Add "Generate Rates" button (`st.button`). Connect UI state to `st.session_state`. Call stubbed backend trigger function.                                           | 5 (FR1, FR2), 7, 9.2  |
| 3            | Triggering Generation & Grid Display | Implement workflow: button click -> show `st.spinner` -> call generation stub -> fetch results stub -> display results in `st.data_editor`. Configure grid columns (`Editable Price`, `Select`, etc.). Show feedback (`st.toast`/`st.success`). | 5 (FR3, FR4, FR5), 9.3 |
| 4            | Detail Pane & Calendar View        | Implement grid selection logic ('View Details' column). Populate detail pane (`st.metric`, etc.) using `get_rate_details` stub. Display calendar view (`st.dataframe`) using pivoted data. Add calendar navigation buttons. Update `focus_date`.        | 5 (FR6, FR7, FR8, FR9), 9.4 |
| 5            | Implementing Actions               | Implement batch selection logic using 'Select' column. Wire up "Adjust", "Approve", "Push Live" buttons (`st.button`) to call corresponding backend stubs. Implement basic validation (`Editable Price`).                                       | 5 (FR10, FR11, FR12, FR14), 9.5 |
| 6            | Backend Integration                | Replace *all* stubs in `utils/backend_interface.py` with actual backend calls (scripts, DB queries, API). Implement caching (`st.cache_data`) for fetch operations. Ensure parameter passing works correctly.                                      | 5, 6, 8, 9.6          |
| 7            | Refinement & Testing               | Implement robust error handling (`try...except`, `st.error`). Add spinners for long actions. Polish UI layout. Perform end-to-end local testing. Document backend config update process.                                                        | 6, 9.7                |

---

## Product Requirements Document (Version 1.1)

**Product Requirements Document: Internal Rate Review & Management Tool MVP**

*   **Version:** 1.1 (Revised based on feedback)
*   **Date:** 2024-07-15
*   **Author/Contact:** [Your Name/Team]
*   **Status:** Final Draft for Approval

**1. Introduction**

This document outlines the requirements for the Minimum Viable Product (MVP) of an internal web-based tool for generating, reviewing, adjusting, and approving hotel room rates. The primary goal is to streamline the day-to-day rate management process for the revenue/pricing team by providing a centralized, user-friendly interface, replacing potentially manual or fragmented workflows. This tool will leverage the existing backend rate generation logic and be implemented using Streamlit for local execution.

**2. Goals**

*   Provide a single interface for triggering rate generation based on user-selected parameters (property, dates).
*   Display generated rates in multiple formats (grid, calendar overview) for effective review.
*   Allow users to review detailed metrics for individual rates.
*   Enable users to edit suggested rates and mark rates for approval via distinct actions.
*   Facilitate the pushing of approved rates to downstream systems via a defined backend mechanism.
*   Improve the efficiency and consistency of the daily rate review process.
*   Serve as a reliable foundation for potential future enhancements.

**3. Scope**

**3.1. In Scope (MVP)**

*   **Frontend Framework:** Streamlit (Requires version >= 1.22.0 for planned component usage).
*   **Deployment:** Local machine execution (`streamlit run app.py`). Requires user to have Python environment and cloned repository.
*   **Configuration:** User selection of Property/Unit Pool(s) and Date Range via the UI.
*   **Rate Generation:** Triggering the *existing* backend rate generation process with parameters selected in the UI.
*   **Data Display:**
    *   Tabular grid view of generated rates using `st.data_editor`. Basic inline editing of designated fields is supported; advanced grid features (e.g., conditional formatting, complex sorting/filtering) are out of scope.
    *   Contextual calendar-like view (±7 days around a focus date) implemented using a pivoted Pandas DataFrame displayed with `st.dataframe`. Visuals will be functional but standard DataFrame style.
    *   Detailed view for a selected rate, showing key metrics (suggested, baseline, occupancy, pace, etc.).
*   **Interaction:**
    *   Inline editing of a designated "Editable Price" field in the `st.data_editor` grid.
    *   Selection of multiple rates in the grid (via dedicated 'Select' checkbox column) for batch actions.
*   **Actions:**
    *   Batch "Approve Selected" rates (marks status).
    *   Batch "Adjust Selected" (uses the edited price from the grid, does *not* automatically approve).
    *   Final "Push Approved Rates Live" action triggering a backend process, with user feedback (spinner). Consider adding a confirmation step (`st.confirm`) if deemed necessary during development.
*   **Backend Interface:** A dedicated Python module (`utils/backend_interface.py`) acting as an abstraction layer.
*   **Basic Feedback:** Loading indicators (`st.spinner`); success/error messages (`st.toast` or `st.success`/`st.error`). Informative error messages for backend failures.
*   **Basic Data Validation:** Validation for `Editable Price` (e.g., non-negative) either in UI or backend.

**3.2. Out of Scope (MVP)**

*   Cloud deployment or shared hosting environments.
*   User authentication, roles, permissions, or multi-user concurrency handling (MVP assumes single-user execution at a time).
*   Data collision resolution between different sessions.
*   Modifications to the core rate generation algorithms or business rules.
*   UI for onboarding new properties or managing backend configuration files (requires manual backend updates, process to be documented separately).
*   Advanced analytics, reporting, or complex data visualizations.
*   Direct PMS integration beyond the defined "Push Live" function.
*   Saving user view preferences or filter settings.
*   Highly customized UI components or advanced grid features.
*   Automated testing framework.
*   Ability to cancel long-running backend operations from the UI.
*   Detailed user-specific audit trails (basic backend logging is recommended).
*   Automated/scheduled rate generation.
*   Advanced grid searching/sorting/grouping capabilities within the UI.

**4. Target Audience**

*   Internal Revenue Management / Pricing Team members. Assumed capable of setting up and running a local Python/Streamlit application from a repository.

**5. Functional Requirements**

| ID    | Requirement Description                                                                                                                                  | Details & Key Components                                                                                                                                                                                                                                                                                                                                                     |
| :---- | :------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR1   | **Configure Rate Generation Parameters**                                                                                                                 | User must select Property/Unit Pools (`st.multiselect`), Start Date (`st.date_input`), End Date (`st.date_input`). Data fetched via `get_available_properties()`.                                                                                                                                                                                                     |
| FR2   | **Trigger Rate Generation**                                                                                                                              | Button (`st.button("Generate Rates")`) triggers `backend_interface.trigger_rate_generation` with UI parameters.                                                                                                                                                                                                                                                 |
| FR3   | **Provide Generation Feedback**                                                                                                                          | Show `st.spinner` during generation. Show informative success (`st.toast`/`st.success`) or error (`st.error`) message on completion, surfacing backend issues clearly if possible.                                                                                                                                                                                      |
| FR4   | **Fetch & Display Generated Rates Grid**                                                                                                                | On success, fetch via `backend_interface.get_generated_rates` and display in `st.data_editor` (key='rate_grid').                                                                                                                                                                                                                                                         |
| FR5   | **Grid Content & Interactivity**                                                                                                                        | Columns: Select (Checkbox), Date, Unit Pool, Suggested, Flag, Baseline, Occ% (Curr), Occ% (Hist), Pace, **Editable Price**, Status, Hidden `_id`. `Editable Price` allows inline number editing. `Select` column enables multi-row selection.                                                                                                                              |
| FR6   | **Display Rate Detail View**                                                                                                                            | Selecting a rate (via 'View Details' checkbox column in grid) populates detail pane via `get_rate_details(rate_id)`. Selection updates `focus_date` for calendar.                                                                                                                                                                                                     |
| FR7   | **Detail View Content**                                                                                                                                  | Display: Unit Pool, Date, Suggested, Current Live, Baseline, Flag Reason, Occ%, Pace using `st.metric`, `st.text`.                                                                                                                                                                                                                                                       |
| FR8   | **Display Contextual Calendar View**                                                                                                                    | Display pivoted DataFrame (`st.dataframe`) showing rates by Unit Pool (rows) vs. Date (columns) for ±7 days around `focus_date` (derived from FR6). Logic requires custom Pandas pivoting.                                                                                                                                                                              |
| FR9   | **Calendar Navigation**                                                                                                                                  | "Previous Week" / "Next Week" buttons (`st.button`) update the calendar's `focus_date`.                                                                                                                                                                                                                                                                                      |
| FR10  | **Batch Rate Adjustment**                                                                                                                                | Button (`st.button("Adjust Selected")`) triggers `backend_interface.update_rates`, passing `_id`s and `Editable Price` values for rows where 'Select' is checked. Adjustment is a distinct action from approval.                                                                                                                                                        |
| FR11  | **Batch Rate Approval**                                                                                                                                  | Button (`st.button("Approve Selected")`) triggers `backend_interface.update_rates`, marking selected (`_id`s) rates as 'Approved' in the backend.                                                                                                                                                                                                                         |
| FR12  | **Push Approved Rates**                                                                                                                                  | Button (`st.button("Push Approved Rates Live")`) triggers `backend_interface.push_rates_live`, passing identifiers for 'Approved' rates. Provide user feedback (spinner). Consider adding confirmation step.                                                                                                                                                           |
| FR13  | **State Management**                                                                                                                                     | Use `st.session_state` to maintain UI selections, generated data, edited grid state between interactions within a single user session.                                                                                                                                                                                                                                      |
| FR14  | **Basic Data Validation**                                                                                                                                | Implement basic validation for `Editable Price` (e.g., must be non-negative). Apply either via `st.data_editor` column config or within `backend_interface.update_rates`.                                                                                                                                                                                           |

**6. Non-Functional Requirements**

*   **Usability:** Intuitive UI following standard Streamlit patterns. Logical workflow.
*   **Performance:** UI rendering should be responsive for expected data volumes (target < 2000 rows). Backend performance depends on existing logic. Use `st.cache_data` for relevant backend fetch calls (`get_available_properties`, `get_generated_rates`, `get_rate_details`) to improve responsiveness. Acknowledge potential `st.data_editor` slowdown with very large datasets (future enhancement: pagination).
*   **Reliability:** Implement `try...except` blocks for backend calls, display user-friendly errors.
*   **Maintainability:** Logical code structure (`app.py`, `utils/`), clear backend interface abstraction. Document backend configuration update process separately.
*   **Dependencies:** Requires Streamlit >= 1.22.0.
*   **Execution Environment:** Designed for single-user, local execution. Concurrency, synchronization, and data collisions are out of scope.
*   **Long-Running Tasks:** No UI mechanism to cancel backend tasks; users must wait or stop the app.

**7. UI/UX Overview**

*   **Layout:** Multi-section Streamlit application (`st.container`): Configuration Area -> Results Area (Calendar, Detail, Grid, Actions).
*   **Key Components:** `st.multiselect`, `st.date_input`, `st.button`, `st.spinner`, `st.toast`/`st.success`/`st.error`, `st.data_editor`, `st.dataframe`, `st.metric`.

**8. Backend Interaction / Data Model**

*   Interface: `utils/backend_interface.py`.
*   **Key Functions & Signatures:** (As defined in previous PRD version, ensure alignment with FRs)
*   **Invocation:** Backend generation process invokable via parameters (e.g., `subprocess.run`).
*   **Data Exchange:** Pandas DataFrames, Python lists/dictionaries.
*   **Change Handling:** `update_rates` likely receives a list of dictionaries representing selected rows with their potentially edited values (`_id`, `Editable Price`, `Status`).

**9. Milestones (Development Phases)**

1.  **Setup & Dependencies:** Initialize project structure (`app.py`, `utils/`), `requirements.txt` (pinned versions), create backend interface stubs (`utils/backend_interface.py`) with hardcoded data.
2.  **Configuration UI & Generation Trigger:** Implement UI for Property/Date selection (`st.multiselect`, `st.date_input`). Add "Generate Rates" button (`st.button`). Connect UI state to `st.session_state`. Call stubbed backend trigger function.
3.  **Triggering Generation & Grid Display:** Implement workflow: button click -> show `st.spinner` -> call generation stub -> fetch results stub -> display results in `st.data_editor`. Configure grid columns (`Editable Price`, `Select`, etc.). Show feedback (`st.toast`/`st.success`).
4.  **Detail Pane & Calendar View:** Implement grid selection logic ('View Details' column). Populate detail pane (`st.metric`, etc.) using `get_rate_details` stub. Display calendar view (`st.dataframe`) using pivoted data. Add calendar navigation buttons. Update `focus_date`.
5.  **Implementing Actions:** Implement batch selection logic using 'Select' column. Wire up "Adjust", "Approve", "Push Live" buttons (`st.button`) to call corresponding backend stubs. Implement basic validation (`Editable Price`).
6.  **Backend Integration:** Replace *all* stubs in `utils/backend_interface.py` with actual backend calls (scripts, DB queries, API). Implement caching (`st.cache_data`) for fetch operations. Ensure parameter passing works correctly.
7.  **Refinement & Testing:** Implement robust error handling (`try...except`, `st.error`). Add spinners for long actions. Polish UI layout. Perform end-to-end local testing. Document backend config update process.

**10. Open Questions / Future Considerations**

*   Confirm expected max number of rate lines to manage UI performance expectations.
*   Finalize backend invocation method (`subprocess.run` preferred for isolation?).
*   Confirm data format/API for `push_rates_live`.
*   Should a confirmation (`st.confirm`) be added before "Push Approved Rates Live"?
*   How should backend generation errors be detailed to the user? (Log file path? Basic message?)
*   *Future:* Pagination/filtering for large grids, advanced sorting/searching, cloud deployment, user auth, audit logs, scheduling.

**11. Success Metrics (MVP)**

*   Successful local execution by target users.
*   Ability to configure, generate, view (grid/calendar/detail), edit, approve, and push rates via the UI.
*   Qualitative user feedback confirming core workflow usability.
*   Demonstrable improvement over previous manual processes. 