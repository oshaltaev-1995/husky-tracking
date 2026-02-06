# System Architecture

## Overview

The demo is implemented as a lightweight web application with a clear separation between user interface, business logic, and data handling. The architecture is intentionally simple to support rapid iteration, transparency, and easy extension.

---

## Main Components

### User Interface (UI)
- Built with **Streamlit**
- Provides interactive dashboards, filters, and visualizations
- Enables data input, configuration of thresholds, and team planning
- Designed for internal kennel use, not public users

---

### Core Services (Business Logic)

The application logic is split into focused service modules:

- **Team Builder**
  - Forms sled teams based on workload constraints
  - Helps distribute work more evenly

- **Fatigue / Workload Logic**
  - Calculates workload indicators
  - Tracks work streaks, rest streaks, rolling workload windows

- **Constraints & Rules**
  - Configurable thresholds for workload limits
  - Transparent rule-based risk detection

This separation allows the logic to be reused later in other interfaces or services.

---

### Data Layer

- Current demo uses **mock and Excel-based data**
- Data structure reflects real kennel records:
  - Daily work entries
  - Distance, work/rest days
  - Dog metadata (age, role)

Planned evolution:
- PostgreSQL database for big structured storage
- Data upload and export functionality
- Historical data preservation and reporting

---

## Data Flow (High-Level)

1. Workload data is imported or entered manually
2. Data is normalized and stored internally
3. Core services compute workload metrics and indicators
4. Results are passed to the UI for visualization
5. User decisions (filters, thresholds, team planning) update the analysis in real time

No external APIs are required for the current demo.

---

## Why this architecture

- Simple and transparent for non-technical users
- Easy to adapt to new data sources
- Supports gradual evolution toward:
  - Database-backed storage
  - Machine learning models
  - Alternative frontends (e.g. Angular)
- Suitable for both academic development and real-world experimentation
