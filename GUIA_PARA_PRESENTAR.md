# EnergyOps: guía para presentar y entender el proyecto

## Qué es el proyecto

**EnergyOps es una aplicación web que permite hacer análisis energético de un edificio mediante preguntas en español.** Está pensada para un administrador que necesita entender cuánto se consume, revisar comportamientos inusuales, decidir cuándo operar ciertas cargas o estimar cuánto tiempo puede funcionar con batería durante un apagón.

Por ejemplo, el usuario puede escribir “¿Cuánto aguanta la batería si solo mantenemos las cargas críticas?”. El sistema interpreta la pregunta, ejecuta la simulación correspondiente y presenta el resultado junto con los parámetros utilizados. Así, el usuario puede consultar sin aprender comandos ni ejecutar cálculos manualmente.

El producto integra dos capacidades: **el LLM interpreta lenguaje natural y las herramientas realizan los cálculos**. Esto permite aprovechar la flexibilidad del modelo para entender distintas maneras de preguntar y conservar un cálculo verificable para los números.

La versión de la feria trabaja con un **edificio de demostración y lecturas sintéticas reproducibles**. El problema corresponde a una necesidad operativa concreta, pero todavía no validamos el producto con un administrador real ni lo conectamos a medidores físicos. Presentamos un prototipo funcional del flujo completo.

### Qué puede hacer

| Función | Pregunta de ejemplo | Resultado útil |
| --- | --- | --- |
| Consultar edificios | “¿Qué edificios puedo analizar?” | Identificación del edificio y sus medidores. |
| Resumir consumo | “Resume el consumo del 2 de marzo de 2026” | Energía consumida, generación solar y demanda máxima y promedio. |
| Detectar anomalías | “Busca consumos raros en los equipos el día de demostración” | Intervalos que conviene investigar por desviarse del comportamiento histórico. |
| Optimizar horarios | “¿A qué hora conviene encender las cargas para pagar menos?” | Horarios propuestos y comparación de costos bajo la tarifa del escenario. |
| Simular un apagón | “Compara el respaldo del edificio y de las cargas críticas” | Minutos de autonomía y condiciones que limitan el respaldo. |

Cada consulta resuelve una tarea principal. Si faltan datos indispensables o la petición está fuera del alcance, el sistema puede pedir una aclaración. Las alertas y simulaciones apoyan el análisis del escenario; no certifican el estado de una instalación.

## Cómo funciona, de principio a fin

### 1. Preparamos la fuente de información

El motor genera un conjunto fijo de **32,832 lecturas**, usando semilla 1337 para poder reproducirlo. Son 57 días de datos: ocho semanas de historia y el día objetivo, **2 de marzo de 2026**. Cada día tiene 96 intervalos de 15 minutos y seis medidores: cinco de consumo y uno solar.

Los circuitos de consumo representan iluminación, aire acondicionado, servicios críticos, bomba y equipos. El motor guarda las lecturas en **SQLite**, una base de datos local. Conserva las marcas de tiempo en UTC y realiza las consultas del escenario con la zona de Guatemala. Mantiene la generación solar separada del consumo para no sumar dos veces la energía.

### 2. El usuario escribe una pregunta

La web recibe el texto y el modelo elegido. Los botones ofrecen preguntas de ejemplo, pero el usuario también puede escribir sus propias palabras. La aplicación limita la entrada a 1,500 caracteres y muestra un estado de espera mientras procesa la consulta.

### 3. El LLM interpreta la tarea

Con **Claude Haiku 4.5**, enviamos la pregunta, las instrucciones del sistema y la descripción de las herramientas disponibles. El proveedor transforma el texto en tokens y ejecuta el modelo. Claude selecciona una herramienta y produce sus argumentos en JSON.

Por ejemplo, “Resume el consumo del 2 de marzo de 2026” se convierte en una llamada como esta:

```json
{
  "name": "get_energy_summary",
  "arguments": {
    "building_id": "demo-building",
    "start": "2026-03-02T00:00:00-06:00",
    "end": "2026-03-03T00:00:00-06:00"
  }
}
```

El límite final del período es exclusivo: se incluye el día 2 completo y se termina justo al iniciar el día 3.

Con **Qwen3 local**, el proceso cambia un poco: el modelo clasifica la intención entre seis etiquetas y un extractor Python obtiene fechas, horas y circuitos mediante reglas. Esa diferencia es importante al explicar la comparación: evaluamos dos soluciones completas con mecanismos de extracción distintos.

### 4. Validamos y llamamos a la herramienta por MCP

Antes de ejecutar, **JSON Schema** comprueba que los argumentos respeten la estructura declarada por la herramienta. El servidor también valida condiciones del problema, como la existencia del edificio o la disponibilidad de lecturas. Un argumento puede tener formato correcto y aun ser inadecuado para la pregunta; por eso también evaluamos las decisiones del modelo.

El cliente **MCP** inicia un proceso local, establece la conexión, descubre las herramientas y envía la llamada. Los mensajes usan **JSON-RPC 2.0 por stdio**: la entrada y salida estándar del proceso transportan solicitudes y respuestas estructuradas. Esta es una conexión real entre procesos, no una simulación de una llamada MCP.

### 5. El motor consulta los datos y calcula

La herramienta elegida lee SQLite y ejecuta su algoritmo. Para consumo suma lecturas y obtiene demanda; para anomalías compara con una referencia histórica; para horarios explora combinaciones permitidas; para apagones simula el balance entre demanda, solar y batería.

El LLM no realiza estos cálculos. En esta implementación tampoco recibe después el resultado para redactar una segunda respuesta: **la aplicación construye el texto visible con plantillas y datos de la herramienta**. Esto reduce la posibilidad de introducir cifras inventadas al redactar, aunque no elimina errores de selección o de argumentos.

### 6. Presentamos una salida que se puede revisar

La web muestra la respuesta, la herramienta utilizada, la latencia y los tokens consumidos. En el detalle se pueden revisar los argumentos y el resultado estructurado. El usuario puede comprobar qué período y edificio se analizaron, en lugar de depender únicamente de una frase del modelo.

Para explicarlo de memoria: **pregunta del usuario → LLM → herramienta y argumentos → validación → MCP → SQLite y algoritmos → resultado en la web**.

## Qué reutilizamos y qué hicimos para esta entrega

Partimos de **EnergyOps, el proyecto de Redes**, porque ya tenía un caso de uso energético, un servidor MCP y un motor de cálculo que podíamos aprovechar. Creamos una copia independiente para Deep Learning. No sería correcto afirmar que construimos todo el motor desde cero durante esta adaptación.

| Parte | Qué hicimos |
| --- | --- |
| Motor energético y datos | Reutilizamos el generador reproducible, SQLite y los algoritmos de consumo, anomalías, optimización y batería de `energyops-mcp`. Conservamos su licencia MIT. |
| Protocolo MCP | Reutilizamos el cliente, servidor y transporte JSON-RPC por stdio. La aplicación nueva usa esa conexión para descubrir e invocar herramientas reales. |
| Producto para la feria | Construimos una interfaz web en español con preguntas de ejemplo, entrada libre, estados de espera, manejo de errores y detalle de cada ejecución. |
| Integración principal con Claude | Adaptamos el flujo a una tarea por consulta, definimos el prompt y expusimos cinco herramientas de análisis. Configuramos tool calling y validación de argumentos. Verificamos la conexión con la nueva credencial. |
| Respaldo con otro LLM | Agregamos Qwen3-0.6B cuantizado Q8_0, ejecutado localmente con llama.cpp, y un flujo de clasificación con extracción por reglas. |
| Presentación de resultados | Agregamos plantillas que muestran los números calculados, convierten horarios de anomalías a Guatemala y explican condiciones como la falta de potencia de la batería. |
| Evaluación | Construimos 30 casos con resultados esperados y un script que compara Claude, Qwen3 y un baseline por palabras clave. Guardamos predicciones, métricas, tiempos y tokens. |
| Verificación | Ejecutamos las pruebas heredadas del motor y protocolo, adaptando la ruta de una fixture al proyecto independiente: 62 pruebas aprobadas. También probamos consumo y apagón desde el navegador con ambos proveedores en los flujos revisados. |
| Material para exponer | Elaboramos el póster científico, esta guía y un video de respaldo de 1 minuto y 35 segundos con uso real del producto. |
| Ejecución y entrega | Agregamos un iniciador para Windows y publicamos el código y los materiales en un repositorio privado, excluyendo credenciales, bases locales y pesos del modelo. |

La contribución de esta entrega consiste en **convertir la base de Redes en un producto web demostrable y medible para un caso de uso de LLM**, con comparación de alternativas y material para explicar el pipeline. No hicimos fine-tuning ni entrenamos un modelo desde cero: la adaptación fue mediante instrucciones y herramientas, técnicas permitidas por el enunciado.

## Cómo responde a los requerimientos del proyecto

El enunciado pide un producto end-to-end con uno o varios LLM, utilizable por terceros, medible y con decisiones justificadas. Para la feria también pide una demostración, un pitch, un diagrama del pipeline y resultados principales. La siguiente relación explica qué podemos mostrar como evidencia y qué sigue limitado.

| Requerimiento del enunciado | Cómo lo abordamos | Evidencia o alcance |
| --- | --- | --- |
| Resolver un problema para un usuario concreto | Definimos al administrador de edificios y las tareas de consumo, alertas, horarios y respaldo. | Las preguntas y salidas están orientadas a decisiones operativas. Falta validar la necesidad y utilidad con usuarios reales. |
| Producto basado en uno o varios LLM | Claude interpreta consultas y extrae argumentos. Qwen3 interpreta intenciones en modo local. | Selector de modelos y ejecución real de inferencia. No se sustituye al LLM por respuestas de ejemplo en el modo en vivo. |
| Flujo end-to-end | Conectamos entrada web, interpretación, validación, MCP, base de datos, algoritmos y salida visible. | Se puede seguir una consulta completa en el detalle de herramienta, parámetros y resultado. No es un notebook suelto. |
| Utilizable por terceros | Una persona puede abrir la web, usar botones o escribir una consulta y leer el resultado. | Interfaz en español y sin necesidad de editar código durante la demostración. Está preparada para probarse en el dispositivo del stand, no como un servicio público en internet. |
| Entender el pipeline de datos | Identificamos fuente sintética, volumen, intervalos, almacenamiento, zona horaria y procesamiento de cada herramienta. | Explicación anterior, código del motor y diagrama del póster. |
| Técnica de adaptación permitida | Usamos prompting y herramientas. | Prompts en `app.py`, esquemas de entrada y llamadas MCP. RAG y fine-tuning son opciones del enunciado, no requisitos obligatorios para todos los proyectos. |
| Conjunto de evaluación propio | Definimos 30 consultas, con cinco por cada una de seis intenciones y su herramienta esperada. | `evaluation/cases.json`. Es el extremo inferior del rango recomendado de 30 a 50; los casos son sintéticos y no tienen validación humana independiente. |
| Medición objetiva de calidad | Calculamos exactitud, F1 macro y comprobaciones de campos críticos de argumentos. Registramos éxito de ejecución MCP. | Resultados por caso en `evaluation/results.json` y `evaluation/results_local.json`. No equivale a medir toda la calidad del producto. |
| Comparación con al menos un baseline | Comparamos con reglas por palabras clave y además con un pipeline de un modelo local más pequeño. | Baseline: 30%; Qwen3: 76.7%; Claude: 100% de exactitud de selección en los mismos 30 casos. |
| Métricas operativas | Registramos latencia, tokens y costo estimado de API. | Para Claude: 2.63 s de media de LLM más ejecución MCP y unos US$0.00225 por caso. Se excluyen conexión inicial, descubrimiento y renderizado de esa media. |
| Justificar decisiones con resultados | Elegimos Claude como principal por su mayor exactitud observada y Qwen3 como respaldo sin internet. Dejamos la aritmética a herramientas especializadas. | Comparación medida y resultados estructurados. El baseline es sencillo y los pipelines difieren en su extracción de argumentos; la conclusión tiene ese alcance. |
| Explicar experimentos y fallas | Conservamos las mediciones de las alternativas y ejemplos de errores de clasificación del modelo local. Identificamos alertas adicionales del detector. | Los archivos por caso permiten revisar fallos. Tenemos una comparación de configuraciones, no un historial extenso de experimentos controlados sobre cada parámetro. |
| Demostración en vivo en al menos un dispositivo | La aplicación puede ejecutar consultas nuevas con Claude y con Qwen3. | `INICIAR.cmd` y navegador del stand. El modo guardado se identifica como respaldo y no debe presentarse como ejecución nueva. |
| Pitch de 3 a 5 minutos | Preparamos una secuencia de problema, demostración, pipeline y métricas. | Se conserva el pitch que aparece más abajo. |
| Póster o presentación con arquitectura y resultados | Elaboramos un póster científico de una página con el recorrido del sistema y la tabla comparativa. | `output/pdf/Poster_EnergyOps.pdf`, su PNG y la vista `/poster`. |
| Dominio técnico de los integrantes | Esta guía explica datos, modelos, herramientas, métricas, decisiones y limitaciones. | La evidencia final será que puedas responder y recorrer una consulta sin depender solo del texto del pitch. |
| Repositorio de GitHub reproducible | Publicamos código, prompts, datos generables, evaluación, pruebas e instrucciones de ejecución. | Repositorio privado indicado al final de la guía. Debes otorgar acceso al catedrático para completar la entrega por ese medio. |
| Video corto de 1 a 3 minutos en MP4 | Grabamos una demostración del uso real y la convertimos a MP4. | `output/demo/Demo_EnergyOps.mp4`, duración aproximada 1:35, sin narración. |
| Trabajo escrito del viernes 6 de noviembre | Quedó fuera del alcance que pediste para hoy. | Esta guía y el póster no sustituyen ese informe ni sus secciones técnicas. Sigue pendiente si se requiere completar la entrega total del curso. |

### Cómo defender los cuatro criterios de la feria

**Creatividad:** mostramos un asistente que ejecuta análisis energético con herramientas y deja revisar la operación realizada. La combinación de consultas, escenarios de batería y comparación de horarios aporta una propuesta concreta para el stand. La originalidad y la puntuación final las juzga el catedrático.

**Utilidad:** las salidas responden preguntas accionables: qué consumo revisar, cuándo mover cargas o qué servicios podrían seguir funcionando. Podemos demostrar esa utilidad dentro del escenario sintético; aún falta medir el beneficio en una operación real.

**Utilizabilidad:** la web permite empezar con un botón, cambiar la pregunta, identificar el modelo y revisar errores y resultados. Incluye respaldo local y ejemplos guardados. Todavía no realizamos un estudio formal de usabilidad con terceros.

**Dominio técnico:** podemos explicar qué hace cada componente y respaldar las métricas con casos y registros. Lo fundamental es distinguir **acierto del LLM al elegir la operación**, **validez de los argumentos**, **correctitud del cálculo** y **utilidad del resultado para una persona**. Son aspectos relacionados, pero una sola métrica no demuestra todos.

Una forma breve de responder “¿por qué este proyecto cumple?” es: “Tenemos un producto web que recibe una consulta, usa un LLM real, ejecuta herramientas MCP sobre datos y devuelve una salida utilizable. Evaluamos la selección de herramientas con 30 casos y la comparamos con un baseline y otro modelo. Podemos demostrar el pipeline y mostrar los resultados en el póster. La validación con usuarios reales y el informe posterior siguen pendientes”.

## Abrir la demostración

1. Haz doble clic en **INICIAR.cmd**. Espera a que abra el navegador.
2. La aplicación está en http://127.0.0.1:8765 y el póster en http://127.0.0.1:8765/poster.
3. Deja **Claude Haiku 4.5** como modelo principal. El segundo modelo, **Qwen3 0.6B**, corre localmente y sirve sin internet. Ya están descargados su modelo y ejecutable en este equipo.
4. Abre el póster PDF de `output/pdf/Poster_EnergyOps.pdf` en otra ventana. Es una sola página horizontal, útil en pantalla o para imprimir conservando proporciones.
5. La clave de Claude está en `.env.local`, excluida de Git. No compartas ese archivo ni la carpeta completa sin filtrar. No hace falta cambiar el proyecto de Redes: esta entrega es independiente y reutiliza su motor MCP bajo MIT.

## Mejoras rápidas para usar durante la feria

El póster actualizado destaca la comparación de modelos con barras, muestra el pipeline horizontal y usa la simulación de batería como ejemplo principal. Conserva las métricas de la evaluación original.

En la aplicación, las cifras principales aparecen en indicadores grandes. Al consultar consumo también se muestra la energía por circuito, con la generación solar diferenciada en otro color. Puedes usar **Copiar respuesta** o **Descargar JSON** para conservar el resultado y sus parámetros. **Ctrl + Enter** ejecuta una consulta desde el campo de texto. El mensaje de espera identifica el modelo seleccionado.

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
