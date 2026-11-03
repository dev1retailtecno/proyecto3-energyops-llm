# EnergyOps · Proyecto 3 Deep Learning

Aplicación para la feria del 2 de noviembre de 2026. Reutiliza el motor y protocolo de [energyops-mcp](https://github.com/iancumes/energyops-mcp) (MIT) en una copia independiente. No requiere modificar Redes ni conectar sus servidores de archivos, Git o inventario.

## Ejecutar

En este equipo: doble clic en `INICIAR.cmd`. Interfaz: http://127.0.0.1:8765. Póster: http://127.0.0.1:8765/poster. La guía es `GUIA_PARA_PRESENTAR.md`.

En otro equipo Windows con Python 3.13 o superior:

```powershell
python -m pip install -r requirements.txt
python setup_local.py
.\INICIAR.cmd
```

`setup_local.py` descarga los pesos oficiales Qwen3 Q8_0 y llama.cpp CPU. Los binarios y pesos están ignorados en Git. El modo local no necesita credenciales. El modo Claude lee `ANTHROPIC_API_KEY` desde `.env.local` o del entorno. Nunca publiques ese archivo. El navegador no recibe la credencial.

## Reproducir resultados

Inicia primero el producto. Después:

```powershell
python evaluate.py
python build_poster.py
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
```

`evaluate.py` ejecuta 30 consultas reales a Claude y 25 llamadas al MCP, por lo que consume API. Los casos y sus etiquetas están en `evaluation/cases.json`. Las predicciones por caso, tokens y tiempos están en `evaluation/results.json`. El benchmark local previo se conserva en `evaluation/results_local.json`. Para repetirlo: `python evaluate.py --local`. Los ejemplos se guardan explícitamente para respaldo, sin hacerse pasar por inferencias nuevas.

La exactitud mide selección de herramienta. La revisión de argumentos valida campos críticos de fecha/edificio/horizonte/bandas, no equivalencia exhaustiva del resultado. Se evaluaron pipelines distintos: Claude extrae argumentos con tool calling, Qwen3 clasifica y usa un extractor por reglas. El baseline busca palabras clave. Los casos son sintéticos, con referencias definidas al redactarlos, sin revisión humana independiente. No se midió calidad general ni tasa de alucinaciones.

## Archivos

- `app.py`: prompts, proveedores, extracción local, cliente MCP, plantillas y HTTP local.
- `index.html`: web de feria y selector de modelos.
- `energyops_mcp/`: motor reutilizado, datos, SQLite, algoritmos y protocolo.
- `evaluate.py`, `evaluation/`: conjunto de evaluación, baseline y resultados medidos.
- `tests/`: pruebas heredadas del motor y protocolo. La ruta de la fixture se adaptó al paquete local.
- `build_poster.py`, `output/pdf/`: generador, póster PDF y vista PNG.
- `GUIA_PARA_PRESENTAR.md`: pitch, demo, resultados y preguntas técnicas.

El conjunto tiene 32,832 lecturas sintéticas, semilla 1337, día objetivo 2026-03-02. Se mantienen separados cinco medidores de consumo y uno solar. No hay RAG, embeddings, fine-tuning ni control de dispositivos físicos. Los algoritmos consideran la resolución de 15 minutos y las condiciones configuradas del escenario.

## Fuentes técnicas

- [MCP: herramientas, especificación 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).
- [Claude Haiku 4.5](https://platform.claude.com/docs/en/models/haiku-4-5/overview).
- [Precios Claude](https://platform.claude.com/docs/en/about-claude/pricing): estimación USD 1/M entrada y USD 5/M salida. No incluye impuestos ni costos de hardware.
- [Pesos oficiales Qwen3-0.6B-GGUF](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF).
- [llama.cpp](https://github.com/ggml-org/llama.cpp), runtime CPU versión b12061.

## Publicación

Esta carpeta es la entrega local de la feria. No contiene el informe del viernes. Antes de publicar, usar `.gitignore`, excluir `.env.local`, bases, logs y `local_runtime/`. El código reutilizado conserva `LICENSE`. El estado del repositorio y del video se registra al completar la entrega; no se debe afirmar publicación remota sin una URL verificada.

Repositorio privado: https://github.com/dev1retailtecno/proyecto3-energyops-llm

Video de respaldo: `output/demo/Demo_EnergyOps.mp4` (grabación de uso real, sin narración). El repositorio es privado: otorga acceso al catedrático antes de entregarlo.

Mejora visual de la feria: póster con gráfica comparativa y pipeline horizontal, indicadores de resultados, gráfica por circuito, copia de respuesta y descarga JSON. El video conserva la interfaz inicial y demuestra el mismo flujo funcional.
