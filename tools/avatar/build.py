# blender -b -P build.py -- <gender m|f> <outdir> [item ...]
# MakeHuman (MPFB2) bilan skeletli (cmu_mb) realistik avatar yasaydi va har bir buyumni alohida GLB qiladi.
import bpy, sys, os, json, importlib

argv = sys.argv[sys.argv.index("--") + 1:]
G, OUT = argv[0], argv[1]
ONLY = set(argv[2:])
os.makedirs(OUT, exist_ok=True)


def imp(pkg, key):
    for m in list(sys.modules):
        if m.endswith(pkg):
            return getattr(importlib.import_module(m), key)
    raise ValueError(pkg)


HumanService = imp("mpfb.services.humanservice", "HumanService")
AssetService = imp("mpfb.services.assetservice", "AssetService")
ExportService = imp("mpfb.services.exportservice", "ExportService")
TargetService = imp("mpfb.services.targetservice", "TargetService")

OUTFITS = ["male_casualsuit01", "male_casualsuit02", "male_casualsuit03", "male_casualsuit04", "male_casualsuit05",
           "male_casualsuit06", "male_elegantsuit01", "male_worksuit01",
           "female_casualsuit01", "female_casualsuit02", "female_elegantsuit01", "female_sportsuit01"]
SHOES = ["shoes01", "shoes02", "shoes03", "shoes04", "shoes05", "shoes06"]
HATS = ["fedora01", "fedora_cocked"]
HAIR = ["afro01", "bob01", "bob02", "braid01", "long01", "ponytail01", "short01", "short02", "short03", "short04"]
ITEMS = [("clothes", n) for n in OUTFITS + SHOES + HATS] + [("hair", n) for n in HAIR]
if ONLY:
    ITEMS = [it for it in ITEMS if it[1] in ONLY]

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

macro = TargetService.get_default_macro_info_dict()
if G == "m":
    macro.update({"gender": 1.0, "age": 0.5, "muscle": 0.62, "weight": 0.52, "height": 0.58, "proportions": 0.7})
else:
    macro.update({"gender": 0.0, "age": 0.5, "muscle": 0.5, "weight": 0.46, "height": 0.5, "proportions": 0.75,
                  "cupsize": 0.5, "firmness": 0.6})
basemesh = HumanService.create_human(macro_detail_dict=macro)
skin = AssetService.find_asset_absolute_path("young_caucasian_%s.mhmat" % ("male" if G == "m" else "female"), asset_subdir="skins")
HumanService.set_character_skin(skin, basemesh, skin_type="GAMEENGINE")
HumanService.add_builtin_rig(basemesh, "cmu_mb")
rig = basemesh.parent

parts = [("eyes", "low-poly.mhclo", "Eyes"), ("eyebrows", "eyebrow001.mhclo" if G == "m" else "eyebrow010.mhclo", "Eyebrows"),
         ("eyelashes", "eyelashes01.mhclo" if G == "m" else "eyelashes02.mhclo", "Eyelashes"),
         ("teeth", "teeth_base.mhclo", "Teeth"), ("tongue", "tongue01.mhclo", "Tongue")]
body_objs = []
for sub, fn, t in parts:
    body_objs.append(HumanService.add_mhclo_asset(AssetService.find_asset_absolute_path(fn, asset_subdir=sub), basemesh,
                                                  asset_type=t, subdiv_levels=0, material_type="GAMEENGINE"))
items = {}
for sub, name in ITEMS:
    p = AssetService.find_asset_absolute_path(name + ".mhclo", asset_subdir=sub)
    o = HumanService.add_mhclo_asset(p, basemesh, asset_type="Clothes" if sub == "clothes" else "Hair",
                                     subdiv_levels=0, material_type="GAMEENGINE")
    o.name = "item_" + name
    items[name] = o
    print("ADDED", name, len(o.data.vertices))

# tanani yashiradigan maskalar → bitlar ("_hide" atributi): klient kiyimga qarab tana uchburchaklarini yashiradi
bpy.context.view_layer.objects.active = basemesh
ExportService.bake_modifiers_remove_helpers(basemesh, bake_masks=False, remove_helpers=True, also_proxy=False)
for m in list(basemesh.modifiers):
    if m.type == "MASK":
        basemesh.modifiers.remove(m)
if basemesh.data.shape_keys:
    bpy.context.view_layer.objects.active = basemesh
    basemesh.select_set(True)
    bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
bits = {}
mask_names = [n for n in OUTFITS + SHOES + HATS if n in items]
attr = basemesh.data.attributes.new("_hide", "FLOAT", "POINT")
vals = [0] * len(basemesh.data.vertices)
for bi, n in enumerate(mask_names):
    vg = basemesh.vertex_groups.get("Delete." + n)
    if not vg:
        continue
    bits[n] = bi
    for v in basemesh.data.vertices:
        for g in v.groups:
            if g.group == vg.index and g.weight > 0.5:
                vals[v.index] |= (1 << bi)
for i, v in enumerate(vals):
    attr.data[i].value = float(v)
for vg in list(basemesh.vertex_groups):
    if vg.name.startswith("Delete."):
        basemesh.vertex_groups.remove(vg)
# kiyim/sochdagi qolgan modifikatorlar (subdiv yo'q) — mask bo'lsa olib tashlaymiz
for o in list(items.values()) + body_objs:
    for m in list(o.modifiers):
        if m.type == "MASK":
            o.modifiers.remove(m)
    if o.data.shape_keys:
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.shape_key_remove(all=True, apply_mix=True)

basemesh.name = "body"


def export(objs, path):
    bpy.ops.object.select_all(action="DESELECT")
    rig.select_set(True)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_skins=True,
                              export_animations=False, export_morph=False, export_attributes=True,
                              export_yup=True, export_apply=False, export_image_format="AUTO",
                              export_extras=False, export_def_bones=False)


export([basemesh] + body_objs, os.path.join(OUT, "base_%s.glb" % G))
for n, o in items.items():
    export([o], os.path.join(OUT, "%s_%s.glb" % (G, n)))
json.dump({"bits": bits}, open(os.path.join(OUT, "meta_%s.json" % G), "w"))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "rig_%s.blend" % G))
print("DONE", bits)
