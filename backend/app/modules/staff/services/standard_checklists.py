"""Ready-made daily checklists for the society's technical staff.

A society defines its own checklist templates (StaffService.create_checklist_template); these are the starting points
for the trades every society employs, so a new society does not begin from a blank page. "Add standard checklists"
copies a chosen one into the society's templates, after which it is the society's own: it can be reworded, have items
added or removed, and is assigned to a duty like any other template (which snapshots its items onto each day's duty).

Each entry is (title, what to look at, required). Required items must be ticked before the duty can be completed.
Every round has to print on ONE page (lines, remarks and signatures), so the lines are short; a test guards that.
"""
from typing import Dict, List, Tuple

Item = Tuple[str, str, bool]

STANDARD_CHECKLISTS: List[Dict] = [
    {
        "code": "plumber_daily",
        "department": "plumbing",
        "name": "Plumber: daily round",
        "description": "The plumber's round of the water supply, pumps, drainage and fire-fighting water, once a day.",
        "items": [
            ("Overhead tanks and underground sump",
             "Level noted for each. Float valves working, no overflow, covers closed.", True),
            ("Water pumps",
             "Run each pump. Listen for noise or vibration; check heat, leaks, pressure gauge.", True),
            ("Water supply to every wing",
             "Pressure on the top floor and farthest flat. Note any wing with low supply.", True),
            ("Leaks and seepage",
             "Basement, terrace, pump room, shafts, stairs: pipes, joints, damp patches.", True),
            ("Common taps, flush tanks and washrooms",
             "Cabin, club, lobby washrooms, garden taps: nothing dripping or running.", True),
            ("Drainage and sewage",
             "Chambers and gullies clear, sump pump working, no smell.", True),
            ("Rainwater and storm-water drains",
             "Terrace, podium and compound drains clear of leaves and silt (monsoon).", False),
            ("Fire-fighting water",
             "Hydrant and riser valves not leaking, jockey pump pressure, tank full.", True),
            ("Water meter and supply received",
             "Main meter reading, and any tanker or borewell supply today.", True),
            ("Residents' plumbing complaints",
             "Attend every open plumbing complaint. Mark it done or note why not.", True),
            ("Tools and spares",
             "Tools returned. Note what is short (washers, tape, fittings).", False),
            ("Handover note",
             "Anything pending, unsafe or to watch for the next shift.", False),
        ],
    },
    {
        "code": "electrician_daily",
        "department": "electrical",
        "name": "Electrician: daily round",
        "description": "The electrician's round: panels, DG set, lights, lifts and safety, once a day.",
        "items": [
            ("Main LT panel, voltage and load",
             "No burning smell, heat or water. Note meter reading, voltage and load.", True),
            ("DG set",
             "Fuel, oil, coolant, battery. Auto (AMF) mode on and ready to start.", True),
            ("Common-area lights",
             "Lobbies, stairs, basement, terrace, compound, gate: replace failed lamps.", True),
            ("Compound and street lights",
             "Timer or photocell switches them on and off on time.", True),
            ("Lifts",
             "Machine room clean and lit, lights and fans work. Log faults.", True),
            ("Water pump starters",
             "Starters and ammeter readings normal. No tripping or buzzing.", True),
            ("Fire alarm, emergency lights and exit signs",
             "Fire panel normal. Emergency lights glow on test.", True),
            ("CCTV, intercom, gate and access control",
             "Power and UPS working. Nothing offline for want of power.", True),
            ("Electrical safety",
             "Panels and DBs locked, no exposed wires, no live work without lock-out.", True),
            ("Residents' electrical complaints",
             "Attend every open electrical complaint. Mark it done or note why not.", True),
            ("Tools, safety gear and spares",
             "Gloves, tester, ladder fit for use. Note lamps, fuses, MCBs short.", False),
            ("Handover note",
             "Anything pending, unsafe or to watch for the next shift.", False),
        ],
    },
    {
        "code": "plumber_electrician_daily",
        "department": "maintenance",
        "name": "Plumber and electrician: daily round",
        "description": "One person's daily round of the water and the power, once a day.",
        "items": [
            ("Water: tanks, sump and supply",
             "Levels noted, float valves work. Pressure OK on top floor and far flat.", True),
            ("Water: pumps",
             "Run each pump. Listen for noise; check heat, leaks, pressure gauge.", True),
            ("Water: leaks, taps and drains",
             "Basement, terrace, pump room, washrooms, garden taps. Drains clear.", True),
            ("Water: sewage and fire-fighting water",
             "Chambers clear, sump pump works. Hydrant valves, jockey pump, tank full.", True),
            ("Power: main LT panel, voltage and load",
             "No burning smell, heat or water. Note meter reading, voltage and load.", True),
            ("Power: DG set",
             "Fuel, oil, coolant, battery. Auto (AMF) mode on and ready to start.", True),
            ("Power: lights",
             "Common areas, compound, gate: replace failed lamps. Timer on time.", True),
            ("Power: lifts and pump starters",
             "Lift machine room clean and lit. Starters and ammeters normal. Log faults.", True),
            ("Power: fire alarm, emergency lights, CCTV",
             "Fire panel normal, emergency lights glow. CCTV, gate have power.", True),
            ("Electrical safety",
             "Panels and DBs locked, no exposed wires, no live work without lock-out.", True),
            ("Residents' water and power complaints",
             "Attend every open complaint. Mark it done or note why not.", True),
            ("Tools, spares and handover note",
             "Tools and gear fit for use. Note spares short and anything pending.", False),
        ],
    },
]

BY_CODE = {c["code"]: c for c in STANDARD_CHECKLISTS}
