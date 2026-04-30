"""
Smart Public Transport Advisor — Hong Kong MTR and Singapore MRT
===============================================
Reads a transport network from a JSON data file and finds/ranks journeys
based on user preferences. Uses official MTR fare lookup table.

Usage:
    python3 transport_advisor.py

Data file:
    hongkong_data.json and singapore_data.json (must be in the same directory)
"""

import json
import os
from collections import defaultdict

def load_network(filepath: str) -> dict:
    if not os.path.exists(filepath):
        print(f"[ERROR] Data file not found: {filepath}")
        exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def build_graph(network: dict) -> dict:
    """
    Build adjacency list from segments list.
    Each edge carries travel time only — cost is looked up from fare table.
    """
    graph = defaultdict(list)
    for seg in network["segments"]:
        a, b = seg["from"], seg["to"]
        if a == b:
            continue
        edge_ab = {"to": b, "line": seg["line"], "duration_min": seg["duration_min"]}
        edge_ba = {"to": a, "line": seg["line"], "duration_min": seg["duration_min"]}
        graph[a].append(edge_ab)
        graph[b].append(edge_ba)
    return graph


def get_fare(network: dict, origin: str, dest: str, fare_type: str) -> float:
    """
    Look up the official fare between origin and dest.
    fare_type: 'adult' (index 0) or 'concessionary' (index 1).

    Lookup strategy:
      1. Direct:   fares[origin][dest]
      2. Reverse:  fares[dest][origin]   (MTR fares are symmetric)
      3. Nearest-hub proxy: find the hub H with the lowest fare to origin,
         then return fares[H][dest].  Used for non-hub <-> non-hub pairs
         where neither stop appears as a fare-table origin.
    """
    idx = 0 if fare_type == "adult" else 1
    fares = network.get("fares", {})

    if origin in fares and dest in fares[origin]:
        return fares[origin][dest][idx]

    if dest in fares and origin in fares[dest]:
        return fares[dest][origin][idx]

    COMPLETE_HUBS = ["KET", "ADM", "CEN", "TST", "MOK", "KOT", "HOK", "HUH", "TAW", "TUM"]
    best_hub = None
    best_cost = float("inf")
    for hub in COMPLETE_HUBS:
        if hub in fares and origin in fares[hub]:
            cost = fares[hub][origin][idx]
            if cost < best_cost:
                best_cost = cost
                best_hub = hub
    if best_hub and dest in fares[best_hub]:
        return fares[best_hub][dest][idx]

    return None  

MAX_SEGMENTS = 40
MAX_ROUTES   = 12

def find_routes(graph: dict, origin: str, destination: str,
                excluded_lines: set = None) -> list:
    """DFS with depth cap. Returns list of routes (each route = list of edge dicts).
    excluded_lines: set of line names to avoid (None or empty = no restriction).
    """
    if excluded_lines is None:
        excluded_lines = set()

    routes = []
    stack = [(origin, [], {origin})]

    while stack and len(routes) < MAX_ROUTES:
        current, path, visited = stack.pop()

        if current == destination and path:
            routes.append(list(path))
            continue

        if len(path) >= MAX_SEGMENTS:
            continue

        for edge in graph.get(current, []):
            neighbour = edge["to"]
            # Skip this edge if its line is in the excluded set
            if edge["line"] in excluded_lines:
                continue
            if neighbour not in visited:
                new_edge = dict(edge)
                new_edge["from_stop"] = current
                new_edge["to_stop"]   = neighbour
                stack.append((
                    neighbour,
                    path + [new_edge],
                    visited | {neighbour}
                ))

    return routes

def score_route(route: list, network: dict, fare_type: str) -> dict:
    """Compute total time, cost (from fare table), segments, lines."""
    origin = route[0]["from_stop"]
    dest   = route[-1]["to_stop"]

    fare = get_fare(network, origin, dest, fare_type)

    if fare is None:
        fare = 0.0
        for seg in route:
            f = get_fare(network, seg["from_stop"], seg["to_stop"], fare_type)
            fare += f if f is not None else 5.0 

    return {
        "total_cost":     round(fare, 1),
        "total_time_min": sum(s["duration_min"] for s in route),
        "total_segments": len(route),
        "lines_used":     list(dict.fromkeys(s["line"] for s in route)),
        "transfers":      max(0, len(dict.fromkeys(s["line"] for s in route)) - 1),
    }


def rank_routes(routes: list, preference: str, network: dict, fare_type: str) -> list:
    scored = [(r, score_route(r, network, fare_type)) for r in routes]

    if preference == "cheapest":
        scored.sort(key=lambda x: (x[1]["total_cost"], x[1]["total_time_min"]))
    elif preference == "fastest":
        scored.sort(key=lambda x: (x[1]["total_time_min"], x[1]["total_cost"]))
    elif preference == "fewest":
        scored.sort(key=lambda x: (x[1]["total_segments"], x[1]["total_time_min"]))
    elif preference == "balanced":
        costs = [s["total_cost"]     for _, s in scored]
        times = [s["total_time_min"] for _, s in scored]
        segs  = [s["total_segments"] for _, s in scored]

        def norm(val, vals):
            lo, hi = min(vals), max(vals)
            return 0.0 if hi == lo else (val - lo) / (hi - lo)

        scored.sort(key=lambda x: (
            norm(x[1]["total_cost"],     costs) +
            norm(x[1]["total_time_min"], times) +
            norm(x[1]["total_segments"], segs)
        ))

    return scored

DIVIDER  = "─" * 64
BOLD_DIV = "═" * 64

LINE_COLORS = {
    # Hong Kong MTR
    "Island":              "🔵",
    "South Island":        "🟡",
    "Tsuen Wan":           "🔴",
    "Kwun Tong":           "🟢",
    "Tseung Kwan O":       "🟣",
    "Tung Chung":          "🟠",
    "East Rail":           "🩵",
    "Tuen Ma":             "🟤",
    "Disneyland Resort":   "🩷",
    # Singapore MRT
    "North South":         "🔴",
    "East West":           "🟢",
    "North East":          "🟣",
    "Circle":              "🟠",
    "Downtown":            "🔵",
    "Thomson East Coast":  "🟤",
}

def stop_label(sid: str, stop_lookup: dict) -> str:
    s = stop_lookup.get(sid)
    return f"{s['name']} ({sid})" if s else sid


def print_route(rank: int, route: list, score: dict,
                stop_lookup: dict, currency: str, fare_type: str):
    fare_label = "Adult" if fare_type == "adult" else "Child/Senior"
    print(f"\n  Route #{rank}  [{fare_label} fare]")
    print(f"  {DIVIDER}")
    for i, seg in enumerate(route, 1):
        icon = LINE_COLORS.get(seg["line"], "⬛")
        frm  = stop_label(seg["from_stop"], stop_lookup)
        to   = stop_label(seg["to_stop"],   stop_lookup)
        print(f"  {i:>2}. {icon} [{seg['line']:<18s}] {frm}  →  {to}")
        print(f"       ⏱  {seg['duration_min']} min")
    print(f"  {DIVIDER}")
    print(f"  TOTAL  ▸  ⏱ {score['total_time_min']} min  |  "
          f"💰 {currency}{score['total_cost']:.1f}  |  "
          f"🔁 {score['transfers']} transfer(s)  |  "
          f"📍 {score['total_segments']} segment(s)")
    lines_str = "  →  ".join(
        f"{LINE_COLORS.get(l,'⬛')} {l}" for l in score["lines_used"]
    )
    print(f"  Lines  ▸  {lines_str}")

def list_stops(stop_lookup: dict):
    print(f"\n  {'ID':<6}  {'Name':<25}  Lines")
    print(f"  {'─'*6}  {'─'*25}  {'─'*35}")
    for sid, s in stop_lookup.items():
        icon  = LINE_COLORS.get(s["lines"][0], "⬛")
        lines = ", ".join(s["lines"])
        print(f"  {sid:<6}  {s['name']:<25}  {icon} {lines}")


def get_stop_input(prompt: str, stop_lookup: dict) -> str:
    while True:
        raw = input(prompt).strip().upper()
        if raw == "LIST":
            list_stops(stop_lookup)
        elif raw in stop_lookup:
            return raw
        else:
            matches = [
                sid for sid, s in stop_lookup.items()
                if raw.lower() in s["name"].lower()
            ]
            if len(matches) == 1:
                print(f"  ✓ Matched: {stop_label(matches[0], stop_lookup)}")
                return matches[0]
            elif len(matches) > 1:
                print(f"  Multiple matches: {', '.join(stop_label(m, stop_lookup) for m in matches)}")
            else:
                print(f"  [!] '{raw}' not found. Type LIST to see all stops, or enter a stop ID/partial name.")


PREFERENCES = {"1":"cheapest","2":"fastest","3":"fewest","4":"balanced"}

def get_preference() -> str:
    print("\n  How would you like to rank routes?")
    print("    1  Cheapest   — lowest fare")
    print("    2  Fastest    — shortest travel time")
    print("    3  Fewest     — fewest segments / transfers")
    print("    4  Balanced   — best overall score")
    while True:
        c = input("  Enter 1–4: ").strip()
        if c in PREFERENCES:
            return PREFERENCES[c]
        print("  [!] Please enter 1, 2, 3, or 4.")


def get_fare_type() -> str:
    print("\n  Fare type:")
    print("    1  Adult (Single Journey Ticket)")
    print("    2  Child / Senior (Concessionary)")
    while True:
        c = input("  Enter 1 or 2: ").strip()
        if c == "1": return "adult"
        if c == "2": return "concessionary"
        print("  [!] Enter 1 or 2.")


def get_excluded_lines(network: dict) -> set:
    """Prompt the user to optionally exclude one or more lines from the search."""
    lines = [l["id"] for l in network.get("lines", [])]
    if not lines:
        return set()

    print("\n  Exclude lines? (press ENTER to skip)")
    print("  Available lines:")
    for i, line in enumerate(lines, 1):
        icon = LINE_COLORS.get(line, "⬛")
        print(f"    {i}  {icon}  {line}")
    print("  Enter line numbers to exclude separated by spaces (e.g. 1 3),")
    print("  or press ENTER to use all lines.")

    raw = input("  Exclude: ").strip()
    if not raw:
        return set()

    excluded = set()
    for token in raw.split():
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(lines):
                excluded.add(lines[idx])
            else:
                print(f"  [!] '{token}' is not a valid line number, skipped.")
        else:
            print(f"  [!] '{token}' is not a valid number, skipped.")

    if excluded:
        icons = "  ".join(f"{LINE_COLORS.get(l,'⬛')} {l}" for l in excluded)
        print(f"  ✗ Excluding: {icons}")
    return excluded

def list_available_networks(data_dir: str) -> list:
    return sorted([f for f in os.listdir(data_dir) if f.endswith("_data.json")])


def choose_network(data_dir: str) -> str:
    available = list_available_networks(data_dir)
    if not available:
        print("[ERROR] No network data files found in:", data_dir)
        exit(1)
    if len(available) == 1:
        return os.path.join(data_dir, available[0])
    print("\n  Available transport networks:")
    for i, fname in enumerate(available, 1):
        print(f"    {i}. {fname}")
    while True:
        c = input("  Choose a network (number): ").strip()
        if c.isdigit() and 1 <= int(c) <= len(available):
            return os.path.join(data_dir, available[int(c) - 1])
        print("  [!] Invalid choice.")

def main():
    data_dir = os.path.dirname(os.path.abspath(__file__))

    print("\n" + BOLD_DIV)
    print("   🚇  Smart Public Transport Advisor")
    print(BOLD_DIV)

    network_file = choose_network(data_dir)
    network      = load_network(network_file)
    graph        = build_graph(network)
    stop_lookup  = {s["id"]: s for s in network["stops"]}
    currency     = network.get("currency", "HKD")
    city_label   = f"{network.get('city','?')} — {network.get('network','?')}"
    fare_date    = network.get("fare_effective_date", "")

    print(f"\n  Loaded : {city_label}")
    print(f"  Stops  : {len(stop_lookup)}   |   Fare chart effective: {fare_date}")
    print(f"  Note   : {network.get('fare_note','')}")

    while True:
        print("\n" + DIVIDER)
        print("  Commands:  PLAN | LIST | SWITCH | QUIT")
        cmd = input("  > ").strip().upper()

        if cmd == "LIST":
            list_stops(stop_lookup)

        elif cmd == "SWITCH":
            network_file = choose_network(data_dir)
            network      = load_network(network_file)
            graph        = build_graph(network)
            stop_lookup  = {s["id"]: s for s in network["stops"]}
            currency     = network.get("currency", "HKD")
            city_label   = f"{network.get('city','?')} — {network.get('network','?')}"
            print(f"\n  ✓ Switched to: {city_label}  ({len(stop_lookup)} stops)")

        elif cmd == "PLAN":
            print(f"\n  Planning a journey on {city_label}")
            print("  (Type LIST or a partial station name at any stop prompt)\n")

            origin      = get_stop_input("  Origin stop ID / name      : ", stop_lookup)
            destination = get_stop_input("  Destination stop ID / name : ", stop_lookup)

            if origin == destination:
                print("  [!] Origin and destination are the same stop.")
                continue

            preference     = get_preference()
            fare_type      = get_fare_type()
            excluded_lines = get_excluded_lines(network)

            excl_note = ""
            if excluded_lines:
                excl_note = "  |  ✗ Excluding: " + ", ".join(excluded_lines)

            print(f"\n  Searching: {stop_label(origin, stop_lookup)}  →  {stop_label(destination, stop_lookup)}")
            print(f"  Preference: {preference.upper()}  |  Fare type: {'Adult' if fare_type=='adult' else 'Child/Senior'}{excl_note}")
            print("  Please wait...\n")

            routes = find_routes(graph, origin, destination, excluded_lines)

            if not routes:
                if excluded_lines:
                    print("  [!] No routes found — journey is impossible without the excluded line(s).")
                    print(f"      Excluded: {', '.join(excluded_lines)}")
                    print("      Try again without excluding those lines.")
                else:
                    print("  [!] No routes found within segment limit.")
                    print(f"      (Max segments: {MAX_SEGMENTS})")
                continue

            ranked = rank_routes(routes, preference, network, fare_type)

            print(f"\n{BOLD_DIV}")
            print(f"  Found {len(ranked)} route(s)  |  Ranked by: {preference.upper()}")
            print(BOLD_DIV)

            top = ranked[:5]
            for i, (route, score) in enumerate(top, 1):
                print_route(i, route, score, stop_lookup, currency, fare_type)

            print(f"\n  Showing top {len(top)} of {len(ranked)} route(s).")

        elif cmd == "QUIT":
            print("\n  Goodbye! 再見 👋\n")
            break

        else:
            print("  [!] Unknown command. Try PLAN, LIST, SWITCH, or QUIT.")


if __name__ == "__main__":
    main()
