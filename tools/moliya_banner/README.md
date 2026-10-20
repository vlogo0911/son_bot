# 💼 Moliya bannerlari (three.js render)

`bank.html` va `birja.html` — 3D sahnalar (seyf eshigi, oltin quymalar, EMP tangalar / shamlar grafigi va oltin strelka) va ustidagi CSS matn.
Yig'ish uchun shu papkaga quyidagilarni qo'ying:
- `three.min.js` (r128);
- `cinzel.ttf` va `jost.ttf` (Google Fonts, OFL);
- `emp_face.webp` (`webapp_assets/` dan).

Keyin `python shot.py bank` va `python shot.py birja` buyruqlarini ishga tushiring (Playwright + Chromium SwiftShader). Natija 1200×600 JPEG bo'ladi. Uni `webapp_assets/moliya_<bank|birja>.jpg` qilib nusxalang.
