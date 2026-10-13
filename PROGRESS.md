# H3FaceRefine — progreso de diagnóstico y fixes (sesiones 2026-10-12)

## ESTADO: auto-alineado del parche (anti-"slide") implementado; falta verificación en vivo.

**Problema:** el pegado es exacto (dx≈0) pero el contenido repintado dentro del parche queda
desplazado unos pocos px (dy≈+3.5, dh≈+2-10 en el vídeo del capitán) → se ve la cara refinada
"deslizándose" sobre la cabeza original.

**Descubrimiento clave:** `transform["face_rect"]` del tracker NO es la posición real de la cara
en el crop: está SIEMPRE centrado en el canvas (`cw/2 - fw/2`). Medición offline del crop real
(576x576, frames 0-2): cara en `x=215 y=104 w=146 h=192` → centro (288, **200**), no (288,288).
Usar face_rect como objetivo daba un desplazamiento de ~88px → rechazado por `max_shift=40`
→ el realign no hacía nada. (El crash `numpy.int64` era un bug del print de debug.)

**Solución (Fase A):** nodo Swarm nuevo `SwarmH3FaceRealign` en
`src/BuiltinExtensions/ComfyUIBackend/ExtraNodes/SwarmComfyCommon/SwarmModels.py`:
- Detecta la cara (YOLO) en el crop de ORIGEN y en el REFINADO, y traslada el refinado para
  que ambos centros coincidan. **Solo traslación** (con barba/sustitución la caja YOLO cambia
  de tamaño y escalar distorsionaría).
- Clamp `max_shift=40px`, suavizado gaussiano por segmentos (cortes), pass-through si falta
  detección o el desplazamiento es irreal.
- **Test offline** (crops reales desplazados a propósito, venv de ComfyUI): residuo
  0.8px con `smooth_frames=1`, 1.6px en un ramp suave, 0.09px sin desplazamiento, y rechaza
  correctamente un salto de 80px. ✓
- C#: param `H3 Face Auto-Align Paste` (default true) + wiring `VAEDecode → Realign → H3FaceStitch`
  pasando `crops` del tracker como `source_crops`.
- PENDIENTE: verificación en vivo (V1 barba den0.5 → medir dy≈0; V2/V3/V4 identidad 0.65/0.75).

---

## ESTADO (ronda anterior): la sustitución de identidad estaba ROTA por refnorm + anchor. Ambos ELIMINADOS.

**Diagnóstico forense de los runs del usuario (runs 39-45, metadata embebida):**
- Run 39/40 (ref crudo, SIN refnorm, SIN anchor): **identidad SÍ transferida** — bigote/grBigote
  del ref A aparece claramente en el capitán (zoom144_src_39_40_42.png).
- Run 41-45 (refnorm H3FaceTrackCrop en el ref + anchor keyframe): **identidad MUERTA** — la cara
  vuelve a ser prácticamente la del actor original (run42 con ref B = barbudo: ni rastro de barba).
- Tests dirigidos P1-P7 (/tmp/opencode/diag/, ComfyUI directo 7821, ~90s c/u):
  - P1 (refnorm SÍ, anchor NO, ref B, den 0.5): SIN barba → refnorm ya mata solo.
  - P4/P5/P6 (refnorm NO, anchor NO): P4 den0.5 = bigote/bigotón visible; P5 den0.65 =
    **BARBA COMPLETA claramente visible**; P6 ref mujer den0.65 = cambio parcial (cara distinta,
    no llega a femenino).
  - P7 (refnorm NO, anchor SÍ, ref B, den0.5): SIN barba → **el anchor por sí solo mata la identidad**.
- Medida del "slide" (YOLO box output vs fuente): dx≈-1px (pegado exacto), dy medio ~+4px,
  dh ~+5-9px (contenido re-render más abajo/alto). Sin anchor (P4): dy 3.8 (similar o mejor que
  con anchor). El residual ~4px es el deslizamiento restante, modesto.
- El "gato en el busto" NO vuelve sin refnorm (runs 39/40 limpios; P1-P7 busto limpio) —
  lo habían arreglado el sanitize + la receta de denoise, no el refnorm.

**Fixes de esta fase (H3FaceRefineExtension.cs, 0 errores de build):**
1. ELIMINADO refnorm: `ref_images.ref_image_0` = retrato crudo (sin H3FaceTrackCrop ni
   ImageFromBatch sobre el ref).
2. ELIMINADO anchor: param `H3 Face Anchor First Frame` borrado; condición = salida cruda de
   MiniMaxH3ReferenceToVideo.
3. REVERTIDO identity-tracking automático: `identity_track=true` solo en el modo explícito
   "Identity Match". El tracker con `largest_face` seguía bien al actor en el vídeo del capitán
   (el busto NO lo secuestró en runs 39-45); el identity-track con un ref de OTRA persona
   es conceptualmente erróneo para sustitución.
4. Textos de denoise actualizados: receta de sustitución = denoise 0.5-0.65 + Large Face 1.0
   + Ref Size max.

**Receta de sustitución (VERIFICADA empíricamente, P4/P5):**
- `H3 Face Ref Image Size = max`
- `H3 Face Denoise = 0.5` (transferencia moderada: barbigote) o `0.65` (identidad fuerte: barba completa)
- `H3 Face Denoise Large Face = 1.0`
- Ref = retrato grande y centrado de la persona Objetivo; el tracker va en `largest_face`.

## ATENCIÓN: el usuario aún NO tiene estos fixes cargados
- SwarmUI nombrakea el DLL de la extensión por el hash de git HEAD y NO lo recompila si ya
  existe (`src/bin/extensions/SwarmExtensionH3FaceRefine/SwarmExtensionH3FaceRefine-5cc57d13.dll`).
- Para cargar los fixes: borrar esa carpeta y reiniciar SwarmUI (recompila solo al arrancar).
- `dotnet build src/Extensions/H3FaceRefine/H3FaceRefineExtension.csproj -c Release` = 0 errores.

## Materiales de diagnóstico
- Workflows dirigidos + runner: `/tmp/opencode/diag/` (run_p.py, P1-P7_*.json, prompt45.json =
  grafo real del run45 del usuario; runs P* en `dlbackend/ComfyUI/output/video/P*_00001_.mp4`).
- Montajes clave: zoom144_src_39_40_42.png (39/40 bigote vs 42 sin), mont_P456.png (P4/P5/P6),
  mont_P4vsP7.png (anchor mata bigote).
- Refs del usuario: ref_39=A (hombre bigote gris, funciona), ref_42=B (barbudo, P5 lo transfiere
  a den0.65), ref_43=C (mujer joven, P6 solo logra cambio parcial a den0.65).
- Vídeo fuente: source45.mp4 = input/0856001-...mp4 (capitán+busto, 294f, 1024x576).
- ComfyUI hoy: puerto **7821** (comfy-mcp OK). Salidas de diag P* en output/video/.

---

## (SUPERADO — mantenido como historial) Slide diagnosticado con refnorm+anchor

## ESTADO anterior: slide de la máscara "diagnosticado y fijado (ref normalizada + anchor frame 0)"

**Hallazgo del capitán (run H3_FaceRefined_00039, 294f, ref=foto cruda del hombre, denoise 0.5, mult 1.0):**
- Correlación de fase global = 0 px → el pegado ES exacto; el slide es CONTENIDO: la gen con
  repintado fuerte re-encuadra la cara hacia la COMPOSICIÓN del retrato crudo (nose/mouth
  deslizando dentro de la máscara) y el busto de mármol dentro del crop hallucina rasgos (gato).
- FIX VERIFICADO (CH/CI/CJ sobre el MISMO vídeo+ref): normalizar el retrato pasándolo por
  H3FaceTrackCrop (cara centrada, ~33% del canvas) → busto limpio, sustitución claramente
  visible y estable; anchor SwarmMiniMaxH3AddKeyframes(first_frame=crop[0]) como segunda valla.
  CJ (ambos) = limpio y estable.
- Workflow diag: /tmp/opencode/diag/{CH_refnorm,CI_keyfirst,CJ_both}.json; salidas en
  dlbackend/ComfyUI/output/diag/. Comparación: cmp5_all.png.

**Receta de sustitución (verificada con variantes F/G + C*):**
- `H3 Face Ref Image Size = max`
- `H3 Face Denoise = 0.45-0.55` (a 0.55 la identidad nueva es claramente visible; arriba ~0.55
  drifts la cabeza)
- `H3 Face Denoise Large Face = 1.0` (¡el default 0.65 mataba el repaint: t_efectivo = 0.38*0.65 = 0.13!)
- En los diag NO había comfy-kitchen / H3SparseAttention / AIMDO (el stack real del usuario sí
  los pone en los runs por SwarmUI). Validar la receta con el stack completo por el botón.

**Fixes implementados ya antes (sesión pasada):** SanitizeFacialPrompt (orphan <Picture> tags),
MiniMaxH3NativeAudioLock wired + feature h3_audio_lock, aviso >362 frames, defaults JS/C#,
param Ref Image Size. *(El "NUEVO ahora" de esa época — param Anchor + refnorm por
H3FaceTrackCrop — se DESCUBRIÓ después que ROMPÍA la identidad y fue ELIMINADO; ver arriba.)*

## (SUPERADO) "tracker se enganchaba al busto; fix = identity-tracking automático"

**Síntoma del usuario (run 00041):** "la máscara está fija, no sigue el movimiento, se ve la cara
original deslizando sobre la de referencia". En el vídeo del capitán el **busto de mármol** tiene
una cara detectable por YOLO y, con `select=largest_face` + sin identity-tracking, el tracker
se quedó con el busto (máscara fija centrada en el busto), ignorando la cara real del actor.

**Fix implementado:** cuando se carga una imagen de referencia, `ProcessFaceStage` activa
`identity_track=true` y usa esa referencia como `identity_reference` para TODOS los modos
de target (no solo el modo explícito "Identity Match"). El tracker buscará entonces la cara que
matchea con la referencia, no la más grande, evitando que estatuas/otras caras secuestren el
pipeline.

## Qué hacer al retomar (pasos del usuario)
1. Borrar la carpeta de builds de la extensión para forzar la recompilación (SwarmUI NO
   recompila si el DLL por hash de git ya existe):
   `rm -rf src/bin/extensions/SwarmExtensionH3FaceRefine/`
2. Reiniciar SwarmUI (recompila la extensión al arrancar).
3. Probar el botón "H3 Face Refine" sobre el vídeo del capitán con:
   - Caso sustitución: ref de OTRA persona + `H3 Face Ref Image Size = max` +
     `H3 Face Denoise = 0.55-0.65` + `H3 Face Denoise Large Face = 1.0`
     (esperar barba/rasgos del ref visibles; den0.65 = identidad fuerte).
   - Caso restauración: sin ref, denoise 0.27-0.30 → la expresión debe conservarse.
4. El "slide" residual medido es ~4px (dx≈0): si sigue molestando, reportar con frames
   concretos — queda como único issue menor conocido.
5. Verificar en los logs de Swarm "MiniMaxH3NativeAudioLock wired" y el report
   `[H3FaceRefine]` en el log de ComfyUI (hoy puerto 7821).

## Contexto
El usuario reporta: sustituir la cara usando una imagen de referencia produce una "careta"
pegada sobre la cara original — sin expresión y que se desliza, no ajusta al movimiento.
Vídeos afectados: cortos Y largos. Modo usado: botón de historial ("H3 Face Refine") +
"Primary Face (Largest)" con imagen de referencia.
Autorizado: instalar ComfyUI-H3-NativeAudioLock y cablearlo (HECHO).

## Estado al pausar
- **Instalado**: `ComfyUI-H3-NativeAudioLock` copiado desde Shrek3OnVH5/MiniMax-H3-NativeAudio-MusicVideo-Workflow
  a `dlbackend/ComfyUI/custom_nodes/` (nodo `MiniMaxH3NativeAudioLock`, confirmado cargado).
- **Backend ComfyUI**: SwarmUI self-start, ahora en puerto **7822** (el 7821 murió tras el
  reinicio y SwarmUI relanzó con puerto nuevo). comfy-mcp tiene COMFYUI_URL=7821 (STALE,
  no sirve para someter; usar comfy-cli en bash con `--host 127.0.0.1 --port 7822`,
  PATH=/home/tonetxo/.venvs/comfy-mcp/bin).
- **Fase 1 (diagnóstico empírico) EN CURSO**: variante A ejecutada y completada (197s).
  Variantes B/C/D definidas pero SIN LANZAR.

## Hallazgos verificados
1. `H3FaceRefineExtension.cs` manda TODO el vídeo en UNA pasada `MiniMaxH3ReferenceToVideo`
   (length sin tope; rango entrenado H3 ~124-362 frames, "longer is untested").
2. Sin `MiniMaxH3NativeAudioLock`: el stream de audio queda a ceros y el modelo AV genera
   audio inventado; el branch de video le atiende → boca/expresión desacoplada.
3. `ref_image_size="match"` reduce el retrato de ref al área del canvas (768px);
   upstream recomienda "max" (2048) para mejor identidad.
4. Params desalineados con el ejemplo oficial del pack: extensión denoise 0.27 + mult
   0.65 vs pack 0.40 + mult 0.35, steps 6 vs 8. Textos del parámetro mezclan t/sigma.
5. `paste_region="face_ellipse"` feather 22 vs pack `face_only` feather 24 (o SAM 4-8).
6. Menores: JS manda denoise 0.25 por defecto vs C# 0.27; `cut_detection` fijo "none".
7. **CLAVE (variante A, report del tracker)**: vídeo de prueba 362f @ 640x1024 —
   `face=189 (52%), body-fallback=173`. La mitad del vídeo NO tiene detección facial real:
   la posición se estima del cuerpo → crops desalineados → la cara refinada se pega
   desplazada = el "deslizamiento". Jitter bajo (2.4 px/frame), no hay dropouts.
8. API-format quirks: prompt keys string PERO refs de link deben ser `["20", 0]` con id
   en string (wrapper SwarmInternalUtil casca con int refs). SaveText builtin necesita
   format ("txt"). SaveVideo: formato anidado `format.codec=comfy "h264"` aceptado;
   combo dinámico. Detectores válidos: `bbox/face_yolov8m.pt`, `segm/person_yolov8m-seg.pt`.

## Fixes implementados (H3FaceRefineExtension.cs, h3_facerefine.js, README)
1. **SanitizeFacialPrompt**: elimina los `<Picture i>/<Video k>/<Audio j>` del prompt original
   (huérfanos en el pase de refine) y re-ancla la imagen de referencia como `<Picture 1>`.
   RAÍZ del "careta sin expresión": prompt estructurado con ordinales desalineados.
2. **MiniMaxH3NativeAudioLock wired** (on-demand con audio del vídeo fuente; live con el
   AttachedAudio del CurrentMedia cuando exista): audio real locked, denoise solo de vídeo.
   Feature `h3_audio_lock` vía NodeToFeatureMap + InstallableFeature con su URL de repo.
3. **Nuevo parámetro `H3 Face Ref Image Size`** (match/max, avanzado): `max` = 2048px
   para identidad fuerte al sustituir por otra persona.
4. Aviso en logs si el vídeo excede 362 frames (rango entrenado de H3). Segments
   descartado por falta de evidencia (los casos malos eran ≤362 frames; validar luego).
5. JS: default denoise del botón unificado 0.27 = C#. Textos del denoise corregidos
   (fracción de ruido, no t/sigma mezclados).

## Forense de los runs reales del usuario (metadata embebida en los mp4)
- `H3_FaceRefined_00001_.mp4` (2 mujeres, denoise 0.38, steps 8, SIN ref, crop 2.5):
  t=9 la sonrisa desaparece → cara genérica neutra = la "careta". Prompt de escena
  genérico + repaint alto sin ancla de identidad.
- `MiniMax_H3_FaceRefined_00002_.mp4` (fantasia/flydron_seg2): prompt structured con
  `<Picture 1..3>` pero NINGUNA imagen conectada — ordinales colgando; resultado OK
  por el rich-text, pero el wiring de ref nunca llegó en ese run.
- Variantes diag A-E en `dlbackend/ComfyUI/output/diag/`: con ref wired + `<Picture 1>`
  la expresión se conserva hasta a denoise 0.40. Sustitución (ref de otra persona,
  match) = transferencia débil → por eso el parámetro `max`.

## Materiales de diagnóstico
- Runner + 4 workflows API-format: `/tmp/opencode/diag/` y **copia duradera en
  `.diag-backup/` dentro de esta carpeta** (run_diag.py, VA_extasis.json, VB_lock.json,
  VC_pack.json, VD_refmax.json). Regenerables con la info del runner (ver hallazgo 8).
- Salidas variante A: `dlbackend/ComfyUI/output/diag/VA_extasis_00001_.mp4` + report TXT.
- Vídeo de prueba: `input/0856001-...minimaxh3minimax_h3_fused_refdelta_r102.mp4`
  (640x1024, 24fps, 362f, CON audio aac), refs en input: `seoanes.jpeg`, `imageleiros.jpeg`.
- UNet: `minimaxh3/minimax_h3_fused_refdelta_r1024_turbo8_mystic07_int8_convrot.safetensors`
  (turbo 8 pasos, la que generó estos vídeos), CLIP `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`
  type=minimax, VAEs `MiniMaxH3/minimax_h3_video_vae_int8_convrot` + `..._audio_vae_fp32`.

## Próximos pasos (si acaso)
- Si vídeos >362 frames muestran degradación tras los fixes, segmentar la pasada en
  ventanas 17k+5 (≤362). Diseño: trocear en `ExecuteFaceRefinementPipeline` con
  `ImageBatch` entre segmentos; el tracker alinea cada segmento a la rejilla solo.
- Path SAM (`H3FaceMaskSAM` + masks al stitch, feather 4-8) como mejora de bordes.

## Siguientes pasos anteriores (ya hechos: ver "Fixes implementados")
## Optimización de rendimiento (2026-10-13)
Pass de optimización en la extensión (sin cambios de comportamiento observable):
1. **Regex compiladas una sola vez** (`MediaReferenceTagRegex`, `WhitespaceCollapseRegex`):
   antes `SanitizeFacialPrompt` re-parseaba los patrones en cada llamada vía `Regex.Replace`.
2. **Caché del escaneo de modelos H3** (`FindCachedH3Model`): buscar un modelo MiniMax H3
   recorría todos los `Program.T2IModelSets` en cada refinado desde el botón de historial.
   Ahora se cachea; invalidación por el evento estático `T2IModelSet<T>.OnChanged` (+ sets
   creados después vía `FDSTreeDictionary.Added`) y revalidación barata con `File.Exists`.
3. **Lecturas de `UserInput` hoisteadas fuera de `ProcessFaceStage`**: `ref_image_size`,
   multiplicadores small/large, auto-align paste y el flag `h3_audio_lock` se leían repetidas
   veces por stage (cada `Get<double>` implica parseo de string). Se leen una vez por request.
   Extra: normalización defensiva de `Ref Image Size` a {match,max} (valores desconocidos →
   "match", el default rápido/barato en VRAM).
4. **Lectura del vídeo fuente**: `FileStream` con buffer de 1MB + `ReadExactly`
   (`FileOptions.SequentialScan`) en lugar del bucle manual chunk-a-chunk; además
   `FileShare.Read` evita bloqueos en lecturas concurrentes.
5. **JS del botón de historial**: `isVideoSrc` usaba `split().pop().toLowerCase()` sobre el
   src completo en cada comprobación de visibilidad del botón (se ejecuta para cada elemento
   de la vista de historial); ahora usa un patrón precompilado anclado al final.
Nota: no hay toolchain .NET en este entorno; verificado con `node --check` (JS), balanceo de
llaves/paréntesis (C#) y revisión manual del diff. Comportamiento de workflow idéntico: los
nodos generados reciben exactamente los mismos valores (con normalización añadida de ref size).
