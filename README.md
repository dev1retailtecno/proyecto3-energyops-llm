# EnergyOps · Proyecto 3 de Deep Learning

**Ian Cumes · 23236 — Javier Valladares · 23045**
UVG · CC3092 · Entrega: 6 de noviembre de 2026

Aplicación web para consultar consumo, anomalías, horarios y respaldo de batería mediante preguntas en español. Claude Haiku 4.5 o Qwen3-0.6B interpretan la consulta; un servidor **MCP real por stdio** ejecuta herramientas sobre SQLite. Los números se calculan en el motor.

## Entregables finales

| Entregable | Archivo |
| --- | --- |
| Informe editable, 18 páginas | [Informe_EnergyOps.docx](output/entrega/Informe_EnergyOps.docx) |
| Mismo informe en PDF | [Informe_EnergyOps.pdf](output/entrega/Informe_EnergyOps.pdf) |
| Póster actualizado | [Poster_EnergyOps.pdf](output/entrega/Poster_EnergyOps.pdf) |
| Demo actual narrada en español, 2:22 | [Demo_EnergyOps.mp4](output/entrega/Demo_EnergyOps.mp4) |
| Explicación, pitch y preguntas | [GUIA_PARA_PRESENTAR.md](GUIA_PARA_PRESENTAR.md) |
| Instrucciones de entrega | [LEEME_ENTREGA.md](LEEME_ENTREGA.md) |

`python scripts/package_release.py` genera el ZIP conjunto después de guardar la versión en Git. Incluye documentos, video, guía y código sin credenciales, pesos ni bases generadas.

## Ejecutar

En este equipo: doble clic en **INICIAR.cmd**. Interfaz: http://127.0.0.1:8765; póster: `/poster`; informe: `/report.pdf`.

En otro equipo Windows con Python 3.13:

```powershell
python -m pip install -r requirements-lock.txt
.\INICIAR.cmd
```

Claude lee `ANTHROPIC_API_KEY` del entorno o de `.env.local`. El ejemplo `.env.example` no contiene una clave. La credencial permanece en el servidor y está excluida de Git. Los botones directos calculan sin credenciales. Qwen3 es opcional:

```powershell
python setup_local.py
.\INICIAR.cmd
```

El instalador descarga pesos oficiales Qwen3-0.6B Q8_0 y llama.cpp CPU b12061. Se guardan en `local_runtime/`, fuera de Git. Configuración local: contexto 2048, ocho hilos y un slot. El inicio de la aplicación continúa si no está instalado.

## Datos y alcance

`dashboard.sqlite3` se genera automáticamente con datos sintéticos. Al corte de entrega tiene **176,256 lecturas**, seis medidores y **306 días completos**, del 5 de enero al 6 de noviembre de 2026, en intervalos de 15 minutos. Cinco circuitos son de consumo y uno solar. Incluso el día actual es simulado, no una medición en tiempo real.

La fecha predeterminada sigue el día de Guatemala. Para reproducir la entrega, definir antes de iniciar los procesos:

```powershell
$env:ENERGYOPS_TODAY = '2026-11-06'
python app.py
```

`runtime.sqlite3` conserva el escenario histórico del 2 de marzo con 32,832 lecturas. Las bases están ignoradas y se regeneran. La extensión conserva el prefijo original del generador.

La motivación provino de un contexto laboral de administración de tiendas, descrito de manera anónima. La demo tiene un edificio simulado. La recepción empresarial comunicada por el equipo es informal; no se presenta como estudio independiente ni como ahorro real medido.

## Resultados finales

Los **60 casos finales** se congelaron en el commit `b71d310` antes de medir; son distintos de los 30 originales y las 24 sondas de desarrollo.

| Pipeline | Herramienta correcta | Tarea y campos críticos | F1 macro |
| --- | --- | --- | --- |
| Palabras clave | 24/60 · 40.0% | No medido | 0.432 |
| Reglas y extracción | 38/60 · 63.3% | 63.3% | 0.658 |
| Qwen3 local | 57/60 · 95.0% | 95.0% | 0.951 |
| Claude Haiku 4.5 | 58/60 · 96.7% | 96.7% | 0.967 |

Evidencia: `evaluation/final_cases.json` y `evaluation/final_results.json`, con parámetros, tokens, tiempos y errores por caso. Raw y reviewed coinciden en esta muestra: no se atribuye una mejora inexistente a la revisión. El control de peticiones múltiples se añadió después y se comprueba por regresión, sin alterar la puntuación del modelo.

Media LLM + MCP: Claude 1.894 s; Qwen3 0.740 s. API de Claude estimada: USD 0.1578 total, USD 0.00263 por caso. Se excluyen arranque, descubrimiento y navegador. Concurrencia Claude 3 y local 1: no es una comparación controlada de velocidad. Hardware y energía no medidos.

El detector se calibró en diez semillas y se probó en otras veinte. Subir el piso de desviación de 0.1 a **0.2 kWh** redujo falsos positivos de 24 a 0, manteniendo 40 verdaderos positivos en 9,600 intervalos sintéticos. Solo cubre el tipo de pico inyectado. Evidencia: `evaluation/detection_results.json`. Auditoría y resultados MCP: `evaluation/release_audit.json`.

Las etiquetas son sintéticas, sin revisión humana independiente. Un acierto adicional no prueba superioridad estadística. No medimos calidad general, ahorro real ni disponibilidad de producción.

## Repetir y verificar

```powershell
python -m pytest tests -q
python scripts/check_http.py
python scripts/audit_release.py
python scripts/evaluate_detection.py
python scripts/evaluate_final.py --output evaluation/repeticion_final.json
```

La última orden requiere ambos modelos disponibles, consume API y no sobrescribe una medición existente. Respuestas y tiempos pueden variar. Los resultados originales se conservan en `evaluation/results*.json`; `robustness_before.json` y `robustness_after.json` documentan el ajuste observado de las 24 sondas, no una prueba imparcial de generalización.

Figuras y póster: `python scripts/build_figures.py` y `python build_poster.py`. Regeneración del informe:

```powershell
python -m pip install -r requirements-report.txt
python scripts/build_report.py
python scripts/render_report.py
```

El renderizado usado ejecuta el renderizador de documentos de Codex con un adaptador de Word y PyMuPDF porque no había LibreOffice. Requiere Windows y Microsoft Word; si el runtime de documentos de Codex está disponible usa su renderizador, y en otro equipo exporta directamente con Word. La fuente está en `docs/INFORME.md`; el DOCX entregado se puede editar directamente sin regenerarlo. Las 18 páginas se renderizaron y revisaron visualmente.

## Continuidad y límites

Automático intenta Claude, Qwen3 y reglas para tareas reconocidas, identificando el modo. Los botones directos usan MCP sin inferencia. Hay límites de espera, reconexión MCP y resultados guardados por coincidencia exacta de herramienta y argumentos. Los datos parciales se advierten; batería y horarios requieren continuidad. Si no puede resolver, conserva la pregunta y ofrece orientación. No se garantiza disponibilidad absoluta.

El servicio escucha solo en `127.0.0.1` y rechaza POST con Origin ajeno. No tiene autenticación multiusuario para exposición pública. No controla equipos ni certifica instalaciones. No se aplicó fine-tuning ni RAG: la adaptación usa prompts, ejemplos, salida estructurada y herramientas.

## Organización y atribución

- `app.py`, `index.html`, `live_data.py`: orquestación, interfaz y cobertura ampliada.
- `energyops_mcp/`: protocolo, SQLite, generador y algoritmos.
- `scripts/`, `evaluation/`, `tests/`: medición, auditoría, regresión y generadores de entregables.
- `docs/`: informe, prompts y guion del video.
- `output/entrega/`: archivos finales para subir.

Se reutilizó [EnergyOps MCP](https://github.com/iancumes/energyops-mcp), con licencia MIT conservada en `LICENSE`. Las fuentes primarias de modelos y protocolo están citadas en el informe.

Repositorio verificado: **https://github.com/dev1retailtecno/proyecto3-energyops-llm**. Es público y permite acceso sin invitación.
