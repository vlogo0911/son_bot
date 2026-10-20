# blender -b rig_<g>.blend -P anim.py -- <clips.json> <out.glb>
# CMU mocap BVH → MakeHuman cmu_mb skeleti: dunyo fazosida suyak yo'nalishlarini moslab retarget qiladi.
import bpy, sys, json, math
from mathutils import Quaternion, Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:]
CLIPS = json.load(open(argv[0]))
OUT = argv[1]
FPS = 30

rig = next(o for o in bpy.data.objects if o.type == "ARMATURE")
for o in list(bpy.data.objects):          # faqat skelet qoladi
    if o is not rig:
        bpy.data.objects.remove(o, do_unlink=True)
for a in list(bpy.data.actions):
    bpy.data.actions.remove(a)
rig.animation_data_clear()
W = rig.matrix_world.copy()
Wq = W.to_quaternion()
bones = rig.data.bones
order = []
def walk(b):
    order.append(b.name)
    for c in b.children:
        walk(c)
for b in bones:
    if b.parent is None:
        walk(b)
D_REST = {b.name: (W @ b.matrix_local).to_quaternion() for b in bones}
D_ARM = {b.name: b.matrix_local.to_quaternion() for b in bones}
D_HEAD = {b.name: (W @ b.matrix_local).translation.copy() for b in bones}
D_DIR = {b.name: ((W @ b.matrix_local).to_3x3() @ Vector((0, 1, 0))).normalized() for b in bones}
def yaw_of(v):
    return math.atan2(v.y, v.x)
d_left = D_HEAD["LeftUpLeg"] - D_HEAD["RightUpLeg"]
d_leg = (D_HEAD["LeftUpLeg"] - D_HEAD["LeftFoot"]).length

def qfix(q, prev):
    return -q if prev is not None and q.dot(prev) < 0 else q

for name, cfg in CLIPS.items():
    bpy.ops.import_anim.bvh(filepath=cfg["file"], rotate_mode="QUATERNION", update_scene_fps=False,
                            update_scene_duration=False, use_fps_scale=False)
    src = bpy.context.object
    src_act = src.animation_data.action if src.animation_data else None
    sb = src.data.bones
    SW = src.matrix_world.copy()
    S_REST = {b.name: (SW @ b.matrix_local).to_quaternion() for b in sb}
    S_HEAD = {b.name: (SW @ b.matrix_local).translation.copy() for b in sb}
    S_DIR = {b.name: ((SW @ b.matrix_local).to_3x3() @ Vector((0, 1, 0))).normalized() for b in sb}
    s_left = S_HEAD["LeftUpLeg"] - S_HEAD["RightUpLeg"]
    Y0 = Quaternion((0, 0, 1), yaw_of(d_left) - yaw_of(s_left))          # dam olish holatidagi yuz yo'nalishi
    Y0i = Y0.inverted()
    scale = d_leg / (S_HEAD["LeftUpLeg"] - S_HEAD["LeftFoot"]).length
    ALIGN = {}
    for n in order:
        if n in S_DIR:
            ALIGN[n] = D_DIR[n].rotation_difference(Y0 @ S_DIR[n])
    act = bpy.data.actions.new(name)
    rig.animation_data_create()
    rig.animation_data.action = act
    srcfps = 120.0
    f0 = 1 + int(cfg.get("start", 0) * srcfps)
    f1 = 1 + int(min(cfg.get("end", 1e9), cfg["dur"]) * srcfps) - 1
    step = srcfps / FPS
    n_out = int((f1 - f0) / step) + 1
    Kc = None
    p_start = None
    prev = {}
    heads = []
    pbs = rig.pose.bones
    for i in range(n_out):
        f = f0 + i * step
        bpy.context.scene.frame_set(int(f), subframe=f - int(f))
        DW = {}
        for b in src.pose.bones:
            mw = SW @ b.matrix
            DW[b.name] = Y0 @ (mw.to_quaternion() @ S_REST[b.name].inverted()) @ Y0i
        hips_w = Y0 @ ((SW @ src.pose.bones["Hips"].matrix).translation)
        if Kc is None:
            lv = DW["Hips"] @ (Y0 @ s_left)
            Kc = Quaternion((0, 0, 1), yaw_of(d_left) - yaw_of(lv)) if cfg.get("face", True) else Quaternion()
            p_start = hips_w.copy()
        tgt = {}
        for n in order:
            if n in DW:
                tgt[n] = Kc @ DW[n] @ ALIGN[n] @ D_REST[n]
            else:
                par = bones[n].parent
                tgt[n] = tgt[par.name] @ D_REST[par.name].inverted() @ D_REST[n]
        frame = i + 1
        for n in order:
            pb = pbs[n]
            ra = Wq.inverted() @ tgt[n]
            par = bones[n].parent
            if par is None:
                basis = D_ARM[n].inverted() @ ra
            else:
                rp = Wq.inverted() @ tgt[par.name]
                basis = D_ARM[n].inverted() @ D_ARM[par.name] @ rp.inverted() @ ra
            basis = qfix(basis.normalized(), prev.get(n))
            prev[n] = basis
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = basis
            pb.keyframe_insert("rotation_quaternion", frame=frame)
        d = Kc @ (hips_w - p_start) * scale
        if not cfg.get("travel", False):
            d.x *= 0.0; d.y *= 0.0
        target_head = Vector((D_HEAD["Hips"].x + d.x, D_HEAD["Hips"].y + d.y, hips_w.z * scale))
        if i == 0:
            z_off = D_HEAD["Hips"].z - target_head.z if cfg.get("ground", "start") == "start" else 0
        target_head.z += z_off
        heads.append(target_head)
    # siljish: boshlanish va oxirini bir joyga keltiramiz (lobbida personaj joyida qoladi)
    if heads and cfg.get("travel", False):
        dx = heads[-1].x - heads[0].x; dy = heads[-1].y - heads[0].y
        for k, h in enumerate(heads):
            r = k / max(1, len(heads) - 1); h.x -= dx * r; h.y -= dy * r
    for k, h in enumerate(heads):
        delta_arm = W.inverted() @ h - W.inverted() @ D_HEAD["Hips"]
        pbs["Hips"].location = D_ARM["Hips"].inverted() @ delta_arm
        pbs["Hips"].keyframe_insert("location", frame=k + 1)
    act.use_fake_user = True
    rig.animation_data.action = None
    bpy.data.objects.remove(src, do_unlink=True)
    if src_act:
        bpy.data.actions.remove(src_act)
    print("CLIP", name, n_out)

# eksport: faqat skelet + barcha action'lar
bpy.context.scene.render.fps = FPS
for pb in rig.pose.bones:
    pb.rotation_quaternion = Quaternion(); pb.location = Vector()
bpy.ops.object.select_all(action="DESELECT")
rig.select_set(True)
bpy.context.view_layer.objects.active = rig
bpy.ops.export_scene.gltf(filepath=OUT, export_format="GLB", use_selection=True, export_animations=True,
                          export_animation_mode="ACTIONS", export_force_sampling=True, export_frame_step=1,
                          export_optimize_animation_size=True, export_def_bones=False, export_yup=True)
print("ANIMS DONE")
