# Society Structure — Wings, Floors, Flats

## Hierarchy

```
Society (1)
  └── Wing (N)          — A, B, C blocks or named buildings
        └── Floor (N)   — 0 = Ground, 1..N = numbered floors
              └── Flat (N) — individual units
```

---

## Backend Models

### Wing (`backend/app/modules/society_structure/models/wing.py`)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | TimestampMixin |
| society_id | UUID FK → societies | required, indexed |
| name | str | required, unique per society |
| code | str | short code e.g. "A", "B" |
| description | str | optional notes |
| total_floors | int | declared floor count |
| flat_count | int | computed via relationship |
| floor_count | int | computed via relationship |
| is_active | bool | soft delete via TimestampMixin |

### Floor (`backend/app/modules/society_structure/models/floor.py`)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | TimestampMixin |
| society_id | UUID FK → societies | required, indexed |
| wing_id | UUID FK → wings | required, indexed |
| floor_number | int | 0 = Ground floor |
| floor_name | str | optional override e.g. "Terrace" |
| flat_count | int | computed via relationship |
| is_active | bool | soft delete |

### Flat (`backend/app/modules/society_structure/models/flat.py`)

| Column | Type | Notes |
|--------|------|-------|
| id | UUID PK | TimestampMixin |
| society_id | UUID FK → societies | required, indexed |
| wing_id | UUID FK → wings | required, indexed |
| floor_id | UUID FK → floors | optional (for floor-filtered queries) |
| flat_number | str | required, unique per wing |
| flat_type | str | e.g. "1BHK", "2BHK" |
| area_sqft | float | optional |
| floor | int | raw floor number on flat record |
| occupancy_status | str | "vacant" / "owner_occupied" / "tenant_occupied" |
| remarks | str | optional notes |
| wing_name | str | denormalized for display |
| is_active | bool | soft delete |

---

## Flutter Models (`mobile/lib/features/society_structure/data/models/structure_models.dart`)

### WingModel

```dart
class WingModel {
  final String id;
  final String name;
  final String? code;
  final String? description;
  final int? totalFloors;
  final String societyId;
  final bool isActive;
  final int flatCount;
  final int floorCount;

  String get displayName => code != null ? '$name ($code)' : name;
}
```

### FloorModel

```dart
class FloorModel {
  final String id;
  final int floorNumber;   // 0 = Ground Floor
  final String? floorName; // optional label override
  final String wingId;
  final String societyId;
  final bool isActive;
  final int flatCount;

  String get displayName;  // "Ground Floor", "1st Floor", ... or floorName if set
}
```

### FlatModel

```dart
class FlatModel {
  final String id;
  final String flatNumber;
  final int? floor;
  final String? flatType;
  final double? areaSqft;
  final String? occupancyStatus;
  final String? remarks;
  final String wingId;
  final String? wingName;  // denormalized for display
  final bool isActive;

  String get displayName;  // "WingName-FlatNumber" or just flatNumber
  bool get isVacant;
}
```

---

## Router Navigation Contract

GoRouter passes model objects in `extra`. The contract is strict — the router builder must always receive the exact type it casts to.

| Route | `extra` type | Cast in builder |
|-------|-------------|-----------------|
| `floorsByWing` | `WingModel` | `state.extra as WingModel` |
| `floorForm` | `Map<String, dynamic>` with keys `wing` (WingModel) and `floor` (FloorModel?) | `state.extra as Map<String, dynamic>` |
| `flatsByWing` | `Map<String, dynamic>?` with keys `wing` (WingModel?) and `floor` (FloorModel?) | `state.extra as Map<String, dynamic>?` |
| `flatForm` | `Map<String, dynamic>?` with keys `flat`, `wing`, `floor` | `state.extra as Map<String, dynamic>?` |
| `flatDetail` | `FlatModel` | `state.extra as FlatModel` |
| `wingForm` | `WingModel?` | `state.extra as WingModel?` |

**Never pass a model object directly to a route that expects a Map.** Bug history: `FloorListScreen` was passing `extra: wing` (WingModel) to `floorForm` which expected `Map<String, dynamic>` — fixed 2026-06-06.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/wings/` | List wings for current society |
| POST | `/api/v1/wings/` | Create wing (Admin/Committee) |
| PATCH | `/api/v1/wings/{id}` | Update wing |
| DELETE | `/api/v1/wings/{id}` | Soft-delete wing |
| GET | `/api/v1/wings/{id}/floors/` | List floors for a wing |
| POST | `/api/v1/wings/{id}/floors/` | Create floor |
| PATCH | `/api/v1/floors/{id}` | Update floor |
| DELETE | `/api/v1/floors/{id}` | Soft-delete floor |
| GET | `/api/v1/flats/` | List flats (filterable by wing/floor) |
| POST | `/api/v1/flats/` | Create flat |
| GET | `/api/v1/flats/{id}` | Flat detail |
| PATCH | `/api/v1/flats/{id}` | Update flat |
| DELETE | `/api/v1/flats/{id}` | Soft-delete flat |

All endpoints enforce `society_id` isolation from the authenticated user's token.
