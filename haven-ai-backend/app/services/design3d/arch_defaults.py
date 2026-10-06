"""
Architectural defaults and the coordinate system shared by every 3D Design
stage. Nothing else in the module should hard-code these numbers.

Plan / model space (all JSON the backend produces or accepts):
    unit    feet
    origin  the plot's front-left corner at ground level (road side = front)
    x       plot width, left -> right as seen from the road
    y       plot depth, front (road) -> back
    heights (elevation, sill, wall height) are feet above ground

GLB / glTF space (the file the browser loads, see gltf_export.py):
    unit    metres (glTF convention), converted with FT_TO_M
    +X      = plan x
    +Y      = up
    +Z      = towards the road, i.e. glTF z = -plan y. The building therefore
              extends into -Z, and a camera standing on the road looking at the
              house sees plan x increasing to its right. glTF's "front" axis is
              +Z, so the house faces the viewer by default and no mirroring
              (which would flip triangle winding) is needed.
"""

FT_TO_M = 0.3048

# ── Storeys, walls and slabs ──
WALL_HEIGHT_FT = 10.0                 # clear height, floor to ceiling
SLAB_THICKNESS_FT = 0.5
EXT_WALL_THICKNESS_FT = 0.75          # 9 inch exterior masonry
INT_WALL_THICKNESS_FT = 0.375         # 4.5 inch interior partition
PARAPET_HEIGHT_FT = 2.5
STOREY_PITCH_FT = WALL_HEIGHT_FT + SLAB_THICKNESS_FT  # floor-to-floor height

# ── Openings ──
DOOR_WIDTH_FT = 3.0
DOOR_HEIGHT_FT = 7.0
WINDOW_WIDTH_FT = 4.0
WINDOW_HEIGHT_FT = 4.0
WINDOW_SILL_FT = 3.0

# ── Stairs ──
STAIR_STEPS = 16

STOREY_LABELS = {1: "Ground Floor", 2: "First Floor"}

# Wall thickness measured from an uploaded drawing is only used when it falls
# in this range; anything else is treated as a measuring error.
PLAUSIBLE_WALL_THICKNESS_FT = (0.25, 1.5)
