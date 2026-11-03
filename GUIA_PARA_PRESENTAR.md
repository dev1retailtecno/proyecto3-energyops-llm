# EnergyOps: guía para presentar y entender el proyecto

## Abrir la demostración

1. Haz doble clic en **INICIAR.cmd**. Espera a que abra el navegador.
2. La aplicación está en http://127.0.0.1:8765 y el póster en http://127.0.0.1:8765/poster.
3. Deja **Claude Haiku 4.5** como modelo principal. El segundo modelo, **Qwen3 0.6B**, corre localmente y sirve sin internet. Ya están descargados su modelo y ejecutable en este equipo.
4. Abre el póster PDF de `output/pdf/Poster_EnergyOps.pdf` en otra ventana. Es una sola página horizontal, útil en pantalla o para imprimir conservando proporciones.
5. La clave de Claude está en `.env.local`, excluida de Git. No compartas ese archivo ni la carpeta completa sin filtrar. No hace falta cambiar el proyecto de Redes: esta entrega es independiente y reutiliza su motor MCP bajo MIT.

## Pitch de 3 a 5 minutos

**0:00 a 0:40. Problema**

“EnergyOps ayuda a un administrador de edificios a revisar consumo, detectar actividad inusual y evaluar horarios o respaldo con batería. Normalmente tendría que revisar lecturas y ejecutar varios cálculos. Aquí puede preguntar en español. Para esta demostración usamos datos sintéticos reproducibles, no datos de una instalación real.”

**0:40 a 1:30. Primera demostración**

Presiona **Consumo**, luego **Analizar con LLM + MCP**.

“Claude interpreta la pregunta, selecciona `get_energy_summary` y genera sus argumentos. El sistema valida esos argumentos y llama al servidor MCP. Los números los calcula Python a partir de SQLite. La respuesta que mostramos es determinista: no volvemos a pedir al modelo que invente o redacte cifras.”

El día de ejemplo da aproximadamente **189.43 kWh de consumo**, **70.20 kWh de generación solar**, **17.42 kW de demanda máxima** y **7.89 kW de demanda promedio**. Consumo y generación se mantienen separados para evitar doble conteo. Un kW es potencia; un kWh es energía acumulada.

Abre **Ver herramienta, parámetros y resultados**. Muestra `building_id`, fechas con UTC-6 y el JSON calculado. Esto es la evidencia del recorrido completo.

**1:30 a 2:20. Una decisión concreta**

Presiona **Apagón** y analiza.

“El respaldo continuo del edificio completo es **0 minutos**, porque desde el primer intervalo la carga supera la potencia que puede entregar la batería. Eso NO significa que esté vacía. Con solo las cargas críticas, el respaldo es **180 minutos, o tres horas**. El motor considera potencia máxima, energía disponible, reserva, eficiencias y solar.”

Si prefieres mostrar **Ahorro**, el resultado de la tarifa ficticia es costo propuesto de **US$29.4474** y ahorro de **US$0.30** frente al horario original. Los inicios propuestos son **09:15 y 00:00** para las dos cargas configuradas. El ahorro es pequeño en este escenario: no lo presentes como gran reducción real.

**2:20 a 3:10. Pipeline en el póster**

“La pregunta pasa por la tokenización del proveedor y por un prompt con las herramientas y sus esquemas. Claude devuelve un nombre de herramienta y argumentos JSON. JSON Schema valida la estructura. Nuestro cliente MCP envía JSON-RPC por stdio a un proceso local. El servidor consulta SQLite, ejecuta los algoritmos y devuelve texto y datos estructurados. La web presenta esos resultados.”

“Adaptamos el modelo mediante prompting y uso de herramientas. No entrenamos ni ajustamos sus pesos. Tampoco usamos embeddings ni RAG, porque la fuente es una base tabular y necesitamos cálculos precisos.”

**3:10 a 4:10. Métricas y límites**

“Comparamos tres métodos sobre los mismos 30 casos sintéticos, con cinco consultas por cada una de seis intenciones. El baseline por palabras clave obtuvo **30% de exactitud y F1 macro de 0.319**. Qwen3 local obtuvo **76.7% y 0.753**. Claude obtuvo **100% y 1.000** en esta muestra. Los 25 casos que requerían herramientas terminaron sin error MCP. Los otros cinco debían solicitar aclaración o rechazar la petición.”

“La latencia media observada para Claude más la ejecución MCP fue de **2.63 segundos**, excluyendo conexión inicial, descubrimiento de herramientas y renderizado web. La web mide también la preparación de su propia conexión, por lo que puede mostrar tiempos mayores. El costo estimado del benchmark fue **US$0.0674**, unos **US$0.00225 por consulta**, usando la tarifa de referencia de US$1 por millón de tokens de entrada y US$5 de salida. La electricidad y el hardware local no están cuantificados.”

“Este 100% mide selección de herramienta y ciertos campos de argumentos en este conjunto, no exactitud universal, satisfacción humana ni una tasa general de alucinaciones. Las referencias se definieron al crear los casos y no tienen validación humana independiente. Se necesita más evaluación con usuarios reales.”

**4:10 a 4:40. Cierre con interacción**

“Puedes escribir una pregunta equivalente con otras palabras y revisar qué herramienta eligió. También podemos cambiar al modelo local. La idea es convertir lenguaje natural en una operación verificable, dejando las cifras a los algoritmos.”

## Preguntas técnicas que te pueden hacer

**¿Qué parte necesita un LLM?** La interpretación de expresiones diferentes con la misma intención y, en Claude, la extracción de los argumentos. Los cálculos no necesitan un LLM. Una interfaz de botones sería suficiente para un conjunto fijo de tareas; la ventaja que estamos evaluando es el acceso con lenguaje natural.

**¿Qué es MCP?** Un protocolo que permite descubrir e invocar herramientas de manera uniforme. El cliente hace `initialize`, `tools/list` y `tools/call`. Usamos JSON-RPC 2.0 por stdio. MCP no es un LLM, no entrena modelos y no genera la respuesta por sí solo.

**¿Cómo son los datos?** Un edificio, cinco circuitos de consumo y un medidor solar. Hay 57 días por 96 intervalos diarios por 6 medidores: **32,832 lecturas**. Ocho semanas son historia y el 2 de marzo de 2026 es el día objetivo. La semilla es **1337**. La fecha es fija para reproducir resultados, aunque la feria sea en noviembre.

**¿Cómo se preprocesan?** Se generan lecturas por circuito cada 15 minutos, se almacenan con marcas UTC, se separa consumo de generación y se agrupan en hora de Guatemala. Los cálculos sensibles a continuidad rechazan series incompletas. Las importaciones del motor validan encabezados, medidores, valores y duplicados; la web de la feria usa solamente el conjunto preparado.

**¿Cómo se detectan anomalías?** Con mediana y desviación absoluta mediana, MAD, del mismo horario y tipo de día en el historial. Hay un pico inyectado de 3.2 kW en equipos entre las 02:00 y 02:30. La herramienta lo encuentra, pero también marca cinco incidentes adicionales no inyectados. Son posibles falsas alarmas: no afirmes que el detector tiene precisión del 100%.

**¿Qué es F1 macro?** Calcula F1 por cada clase y promedia dando el mismo peso a cada una. F1 combina precisión y recall. Exactitud es aciertos divididos entre casos. Aquí hay seis clases balanceadas y el archivo de resultados conserva cada predicción.

**¿Qué compara el baseline?** Un método sencillo, fijo, que busca palabras como “edificio”, “consumo”, “anomal”, “horario” o “bater”. Es un baseline débil y transparente. No demuestra superioridad frente a todos los métodos clásicos: sería útil compararlo después con un clasificador entrenado o reglas más completas.

**¿Cómo se midieron argumentos?** Además de validar el esquema, el benchmark comprueba identificación del edificio y campos críticos: fecha, límites del día, inicio y horizonte del apagón o cantidad de bandas tarifarias. Es una revisión parcial de campos, no equivalencia semántica exhaustiva de todo JSON. La ejecución MCP aporta una comprobación adicional de validez operacional, no de pertinencia de la intención.

**¿Qué modelo usas y por qué?** Claude Haiku 4.5 (`claude-haiku-4-5-20251001`) es el principal porque obtuvo mejor resultado en esta prueba y permite tool calling. Es cerrado: su número exacto de parámetros y arquitectura no se afirman. Qwen3-0.6B es abierto, denso, de aproximadamente 0.6 mil millones de parámetros, cuantizado Q8_0, licencia Apache 2.0. Corre en CPU con llama.cpp. No afirmes que entrenaste ninguno.

**¿Los dos modelos hacen lo mismo?** Ambos seleccionan entre las mismas intenciones. Claude selecciona la herramienta y sus argumentos mediante tool calling. Qwen3 local clasifica una etiqueta con salida JSON restringida y reglas Python extraen fechas, circuitos y horas. La comparación es entre dos pipelines, no una comparación aislada de modelos con idéntico extractor.

**¿Prompts, parámetros y contexto?** En `app.py` están `CLAUDE_SYSTEM` y `LOCAL_SYSTEM`. Claude usa temperatura 0, máximo 700 tokens de salida y una herramienta por consulta. Qwen3 usa temperatura 0, máximo 30 tokens, thinking desactivado y contexto de 2,048 tokens. Limitamos la pregunta a 1,500 caracteres. No hay memoria conversacional: cada consulta empieza desde cero. En el benchmark Claude consumió 52,698 tokens de entrada y 2,940 de salida en total, unos 1,757 y 98 por consulta. El límite de salida es un máximo, no consumo fijo.

**¿Cómo evitas alucinaciones y prompt injection?** El prompt delimita el alcance, solo se exponen cinco herramientas de análisis, se validan argumentos y la respuesta visible sale de plantillas con datos del motor. No se publican herramientas de archivos, importación ni escritura en la web. Eso reduce riesgos, pero el modelo aún puede elegir una herramienta equivocada o inventar un argumento que pase el esquema. Los casos de seguridad del benchmark son pocos y no prueban protección completa.

**¿Qué datos salen de la computadora?** Con Claude, salen la consulta, el prompt y los esquemas de herramientas. El resultado numérico MCP se procesa y presenta localmente, sin una segunda llamada al proveedor. Con Qwen3 la consulta y la inferencia quedan locales. La demostración usa datos sintéticos y no controla equipos eléctricos.

**¿Qué mejoras siguen?** Validar tareas con administradores reales, ampliar y separar desarrollo y prueba, revisar referencias con un humano independiente, evaluar falsos positivos de anomalías, comparar con un baseline más fuerte y agregar gráficos temporales y un flujo seguro de datos reales.

## Respaldo si falla algo

- Si Claude falla, selecciona **Qwen3 0.6B local**. Prueba “Resume el consumo del 2 de marzo de 2026”. Tiene menor exactitud, por eso no es el principal.
- En **Respaldo para la feria**, abre un resultado guardado. El encabezado lo identifica como respaldo: no lo presentes como inferencia en vivo.
- Si cierras todo, ejecuta `INICIAR.cmd`. Arranca el servidor local oculto y abre la aplicación. No depende de Docker, PostgreSQL ni los otros proyectos de Redes.
- Si el puerto está ocupado por esta misma aplicación, el iniciador la reutiliza.
- No uses “hoy” como fecha de datos. El día disponible de demostración es **2026-03-02**. Fechas sin lecturas pueden producir errores y no deben fabricar resultados.

## Qué está listo para hoy

Producto web, Claude en vivo, Qwen3 local, MCP real, dataset reproducible, 30 casos con métricas, baseline, póster PDF/PNG y esta guía. No se preparó el informe técnico del viernes 6 de noviembre. El repositorio privado es https://github.com/dev1retailtecno/proyecto3-energyops-llm y el video de respaldo está en `output/demo/Demo_EnergyOps.mp4`. Otorga acceso al catedrático antes de entregar el enlace. La rúbrica final depende del catedrático: no hay garantía de nota por las métricas de esta muestra.
