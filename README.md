# restraurant-reservation-bot-GEN-AI-

⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻

A simple, fast, and accurate restaurant reservation system built using FastAPI.
It offers a modern web UI with a powerful backend to manage table availability, bookings, modifications, cancellations, and menu viewing — without guessing or fake availability.

⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻

✨ What This Project Does

✅ Displays real available time slots
✅ Allows users to:
	•	🔍 Check availability
	•	🪑 Book a table
	•	✏️ Modify a reservation
	•	❌ Cancel a reservation
	•	📋 View the restaurant menu

✅ Interaction methods:
	•	🧭 Buttons & forms (primary)
	•	💬 Optional chat input

✅ Entire application runs from one Python file

⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻

🧩 Key Features

🌐 Web Interface
	•	🎨 Clean and responsive UI
	•	🧾 Simple inputs (Guests, Date, Time, Name)
	•	🆔 Reservation reference ID support
	•	🔄 Live availability refresh

⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻

⚙️ Backend Logic
	•	⏱️ Slot-based scheduling
	•	🪑 Seat-capacity validation
	•	🚫 Turn-time blocking (no overlapping tables)
	•	⚡ Fast in-memory caching
	•	👤 Session-aware interactions

⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻

📋 Menu System
	•	📝 Short menu view (item names only)
	•	📖 Detailed menu view (with descriptions)
	•	🗜️ Compact and efficient data storage
⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻

### 🏗️ System Architecture

```mermaid
flowchart TD
    %% Node Definitions
    U(fa:fa-user User / Browser)
    UI[[fa:fa-desktop Web UI]]
    API{{"fa:fa-gears FastAPI Backend"}}
    
    subgraph Logic_Layer [Action Controller]
        direction TB
        CTRL[fa:fa-route Request Router]
    end

    subgraph Engines [Processing Engines]
        AV[fa:fa-calendar-check Availability]
        BK[fa:fa-plus-circle Booking]
        MD[fa:fa-pen-to-square Modify]
        CN[fa:fa-trash-can Cancel]
        MN[fa:fa-utensils Menu Handler]
    end

    subgraph Data_Storage [Data & Config]
        SCH[Slot Scheduler]
        CFG[(Restaurant Config)]
        CACHE[(Availability Cache)]
        STORE[(In-Memory Reservations)]
        MENU[(Menu JSON)]
    end

    %% Connections
    U --> UI
    UI --> API
    API --> CTRL

    CTRL --> AV & BK & MD & CN & MN

    AV --> SCH
    SCH --> CFG
    AV --> CACHE

    BK & MD & CN --> STORE
    MN --> MENU

    %% Styling
    style U fill:#f9f,stroke:#333,stroke-width:2px
    style API fill:#05998b,color:#fff,stroke-width:2px
    style CTRL fill:#fff9c4,stroke:#fbc02d
    style STORE fill:#e1f5fe,stroke:#01579b
    style CACHE fill:#e1f5fe,stroke:#01579b
    style MENU fill:#e1f5fe,stroke:#01579b
