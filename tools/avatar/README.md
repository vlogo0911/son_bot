# 3D avatar yig'ish (web app → Profil → 3D avatarim)

Natija: `webapp_assets/av_*.glb` (bot `WEBAPP_ASSETS` ga avtomatik qo'shadi).

1. Blender 4.2 LTS + MPFB2 (`makehumancommunity/mpfb2`, extension sifatida o'rnatiladi) +
   `makehuman_system_assets_cc0.zip` (MPFB foydalanuvchi `data/` papkasiga ochiladi).
2. `blender -b -P build.py -- m out_m` va `-- f out_f` — tana (`base_<g>.glb`, `_HIDE` bit atributi), har bir kiyim/poyabzal/
   shlyapa/soch alohida skinned GLB (cmu_mb skeleti), `rig_<g>.blend`.
3. CMU mocap BVH (`Shriinivas/cmubvh`, CMU — cheklovsiz) `bvh/` ga; `clips.json` dagi `file` ni `bvh/<nom>.bvh` qiling.
   `blender -b out_<g>/rig_<g>.blend -P anim.py -- clips.json out_<g>/anims_<g>.glb` — dunyo fazosida retarget, 30 fps.
4. `opt.sh in.glb out.glb [2048|1024]` (prune/weld/resize/webp/quantize — `_HIDE` kvantlanmaydi/meshopt);
   animatsiyalar: `gltf-transform resample` + `meshopt`. Fayllar `av_` prefiksi bilan `webapp_assets/` ga.

Litsenziya: MakeHuman system assets — CC0; CMU Graphics Lab Motion Capture Database — cheklovsiz foydalanish.
