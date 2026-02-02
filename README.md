# 🍽️ Restaurant Reservation Bot (Gen-AI)

<div align="center">

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![Uvicorn](https://img.shields.io/badge/Uvicorn-202020?style=for-the-badge&logo=uvicorn&logoColor=white)

**A high-performance, precision-engineered reservation system.** *No "hallucinated" availability—just real-time data, lightning-fast responses, and a sleek modern interface.*
</div>

---

## ✨ What This Project Does

A simple, fast, and accurate restaurant reservation system built using **FastAPI**. It offers a modern web UI to manage table availability without guessing or fake availability.

✅ **Real-time Availability** – Displays actual open time slots.  
✅ **Full Lifecycle** – Check, Book, Modify, and Cancel reservations.  
✅ **Digital Menu** – Detailed item views with compact data storage.  
✅ **All-in-One** – Entire application runs from a single Python file.

---

## 🏗️ System Architecture

The following diagram illustrates the flow from user interaction through the logic engines to the in-memory data store.

```mermaid
flowchart TD
    %% Node Definitions
    U(fa:fa-user User / Browser)
    UI[[fa:fa-desktop Web UI]]
    API{{"fa:fa-bolt FastAPI Backend"}}
    
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

    %% Dark-Mode Optimized Styling
    style U fill:#ff00ff,stroke:#fff,stroke-width:2px,color:#fff
    style API fill:#00ffcc,stroke:#00b38f,stroke-width:2px,color:#000
    style CTRL fill:#ffff00,stroke:#cca300,color:#000
    style Engines fill:#1a1a1a,stroke:#444,color:#fff
    style Data_Storage fill:#1a1a1a,stroke:#444,color:#fff
    style STORE fill:#00d2ff,stroke:#0086a3,color:#000
    style CACHE fill:#00d2ff,stroke:#0086a3,color:#000
    style MENU fill:#00d2ff,stroke:#0086a3,color:#000
