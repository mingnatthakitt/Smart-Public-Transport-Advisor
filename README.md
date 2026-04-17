# COMP1110-Project
# 🚇 Smart Public Transport Advisor

A command-line journey planner for the **Hong Kong MTR** and **Singapore MRT** networks. Given an origin and destination station, it finds multiple routes and ranks them by your preferred criterion — cheapest, fastest, fewest stops, or a balanced score.

---

## Features

- **Multi-network support** — switch between Hong Kong MTR and Singapore MRT at runtime
- **Route finding** — DFS-based search with a configurable segment cap
- **Flexible ranking** — sort results by fare, travel time, number of segments, or a balanced composite score
- **Official fares** — adult and concessionary (child/senior) fare lookup from bundled fare tables
- **Line exclusion** — optionally avoid specific lines when planning a journey
- **Station search** — look up stations by ID or partial name; list all stations in the network

---

## Requirements

- Python 3.7+
- No third-party dependencies — standard library only

---

## Project Structure

```
.
├── transport_advisor.py     # Main application
├── hongkong_data.json       # Hong Kong MTR network data & fares
├── singapore_data.json      # Singapore MRT network data & fares
└── README.md
```

---

## Usage

Run the advisor from the directory containing the data files:

```bash
python3 transport_advisor.py
```

On startup you will be prompted to choose a network. Once loaded, the following commands are available at the main prompt:

| Command  | Description                                      |
|----------|--------------------------------------------------|
| `PLAN`   | Plan a journey between two stations              |
| `LIST`   | List all stations and their lines                |
| `SWITCH` | Switch to a different transport network          |
| `QUIT`   | Exit the program                                 |

### Planning a Journey

When you run `PLAN`, you will be asked for:

1. **Origin** — station ID (e.g. `RAF`) or a partial name (e.g. `raffles`)
2. **Destination** — same format as above
3. **Ranking preference** — one of:
   - `1` Cheapest — lowest fare first
   - `2` Fastest — shortest travel time first
   - `3` Fewest — fewest segments/transfers first
   - `4` Balanced — best combined score across all three factors
4. **Fare type** — `1` Adult or `2` Child/Senior (concessionary)
5. **Line exclusions** — optionally skip one or more lines

The top 5 routes (out of up to 12 found) are then displayed with full breakdown: per-segment line and duration, total time, fare, transfers, and lines used.

---

## Network Data Format

Each `*_data.json` file has the following top-level keys:

| Key                   | Description                                              |
|-----------------------|----------------------------------------------------------|
| `city`                | City name                                                |
| `network`             | Network name (e.g. `"MTR"`, `"MRT"`)                    |
| `currency`            | Currency code used for fares (e.g. `"HKD"`, `"SGD"`)    |
| `fare_effective_date` | Date the fare table came into effect                     |
| `fare_note`           | Human-readable note about fare conditions                |
| `lines`               | Array of line objects (`id`, `name`, `color`)            |
| `stops`               | Array of stop objects (`id`, `name`, `lines`)            |
| `transfer_stations`   | Array of stop IDs that are interchange stations          |
| `connections`         | Interchange metadata per transfer station                |
| `segments`            | Directed edges: `from`, `to`, `line`, `duration_min`     |
| `fares`               | Nested fare table: `fares[origin][dest] = [adult, conc]` |

---

## Supported Networks

### Hong Kong MTR
| Line               | Colour |
|--------------------|--------|
| Island             | 🔵     |
| South Island       | 🟡     |
| Tsuen Wan          | 🔴     |
| Kwun Tong          | 🟢     |
| Tseung Kwan O      | 🟣     |
| Tung Chung         | 🟠     |
| East Rail          | 🩵     |
| Tuen Ma            | 🟤     |
| Disneyland Resort  | 🩷     |

### Singapore MRT
| Line                  | Colour |
|-----------------------|--------|
| North South           | 🔴     |
| East West             | 🟢     |
| North East            | 🟣     |
| Circle                | 🟠     |
| Downtown              | 🔵     |
| Thomson-East Coast    | 🟤     |

---

## Adding a New Network

To add a new city, create a `<cityname>_data.json` file in the same directory following the data format described above. The advisor will detect it automatically on the next run.

---

## Notes

- Fares are looked up end-to-end from the bundled fare table. For station pairs not directly listed, a nearest-hub proxy is used.
- Singapore EZ-Link card fares are approximately 10–15% lower than the single-trip token fares stored in the data file.
- The route search has a cap of **10 segments** and returns up to **12 candidate routes** before ranking.
