"""Export house.blend to walk/house.glb for the walk-through page.

Run (about 20 s):
  "C:\\Program Files\\Blender Foundation\\Blender 4.5\\blender.exe" -b ..\\house.blend -P export_glb.py

Never saves house.blend. Procedural materials cannot travel in glTF, so each
linked Base Color is replaced (in memory only) by one representative flat colour.
Meshes whose material is in NO_COLLIDE get the glTF extra "nocollide" so the
page leaves them out of the collision mesh.
"""
import os
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "house.glb")

# Flat colours for procedural materials whose node default is meaningless (linear RGB).
FLAT = {
    "Gatsten": (0.30, 0.29, 0.27),
    "Grus ljusgrått": (0.52, 0.51, 0.48),
    "Kalksten golv": (0.62, 0.60, 0.55),
    "Kalksten vägg längs X": (0.66, 0.64, 0.59),
    "Kalksten vägg längs Y": (0.66, 0.64, 0.59),
    "Skiffer": (0.10, 0.10, 0.11),
    "Skärm": (0.55, 0.45, 0.35),
}
GLASS = {"Glas": 0.22, "Duschglas": 0.15}
NO_COLLIDE = {"Höjdkurva", "Tomtgräns", "Låga", "Låga.001", "Vatten", "Downlight"}


def ramp_avg(nt):
    for n in nt.nodes:
        if n.type == "VALTORGB":
            els = n.color_ramp.elements
            return tuple(sum(e.color[i] for e in els) / len(els) for i in range(3))
    return None


for m in bpy.data.materials:
    if not m.use_nodes:
        continue
    nt = m.node_tree
    p = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if p is None:
        continue
    bc = p.inputs["Base Color"]
    if bc.is_linked:
        col = FLAT.get(m.name) or ramp_avg(nt) or tuple(bc.default_value[:3])
        for link in list(bc.links):
            nt.links.remove(link)
        bc.default_value = (*col, 1.0)
    # Drop bump/normal links: the exporter cannot bake procedural bump anyway.
    nrm = p.inputs.get("Normal")
    if nrm is not None:
        for link in list(nrm.links):
            nt.links.remove(link)
    if m.name in GLASS:
        p.inputs["Transmission Weight"].default_value = 0.0
        p.inputs["Alpha"].default_value = GLASS[m.name]
        p.inputs["Base Color"].default_value = (0.6, 0.7, 0.75, 1.0)
        m.blend_method = "BLEND" if hasattr(m, "blend_method") else None
        if hasattr(m, "surface_render_method"):
            m.surface_render_method = "BLENDED"

bpy.ops.object.select_all(action="DESELECT")
n = 0
for o in bpy.data.objects:
    if o.type != "MESH" or o.hide_render or not o.visible_get():
        continue
    mats = {s.material.name for s in o.material_slots if s.material}
    if mats and mats <= NO_COLLIDE:
        o["nocollide"] = 1
    o.select_set(True)
    n += 1

bpy.ops.export_scene.gltf(
    filepath=OUT,
    export_format="GLB",
    use_selection=True,
    export_apply=True,
    export_extras=True,
    export_yup=True,
    export_lights=False,
    export_cameras=False,
    export_materials="EXPORT",
)
# Walk-through openings: every opening that starts at a floor (plan 1 at 0, plan 2 at ~3.0).
# The page drops collision triangles that lie wholly inside these boxes, so closed door leaves
# and floor-level glass can be walked through while the wall and the reveals still block.
import json
H = json.load(open(os.path.join(HERE, "..", "house.json"), encoding="utf-8"))
legend = {"E_main": ("y", 0.0, +1), "E_cross": ("y", -3.196, +1), "W_main": ("y", 6.448, -1),
          "W_cross": ("y", 10.249, -1), "N": ("x", 17.946, -1), "N_cross": ("x", 17.645, -1),
          "S_main": ("x", 0.0, +1), "S_cross": ("x", 11.198, +1)}
T, PAD = H["walls"]["thickness"], 0.04
doors = []
for o in H["openings"]:
    z0, z1 = o["z"]
    if not (z0 <= 0.05 or abs(z0 - 3.0) < 0.1):
        continue
    axis, face, inward = legend[o["wall"]]
    d0, d1 = sorted((face - inward * 0.3, face + inward * (T + 0.3)))
    # Along the wall the box reaches 5 cm past the opening: leaf rails span the full width, and the
    # wall reveals still survive because their corners sit exactly at the opening's z0/z1, outside the box.
    a0, a1 = o["a"][0] - 0.05, o["a"][1] + 0.05
    box = [a0, a1, d0, d1] if axis == "y" else [d0, d1, a0, a1]   # Blender x0,x1,y0,y1
    doors.append({"id": o["id"], "box": box + [z0 + PAD, z1 - PAD]})
json.dump(doors, open(os.path.join(HERE, "doors.json"), "w"), indent=1)
print("DOORS", [d["id"] for d in doors])

print(f"EXPORTED {n} meshes -> {OUT} ({os.path.getsize(OUT) / 1e6:.1f} MB)")
