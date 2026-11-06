# Resumen

Desarrollamos EnergyOps para que un responsable de instalaciones pueda realizar análisis energético mediante preguntas en español. El producto conecta una interfaz web con Claude Haiku 4.5 o Qwen3-0.6B, valida los argumentos generados y ejecuta herramientas MCP sobre SQLite. Los algoritmos realizan las operaciones numéricas y las plantillas presentan resultados, con evidencia de la herramienta y los parámetros utilizados.

La versión de entrega contiene 176,256 lecturas sintéticas de seis medidores, distribuidas en 306 días hasta el 6 de noviembre de 2026. En 60 casos nuevos y balanceados, Claude seleccionó correctamente la herramienta y los campos críticos en 58 casos; Qwen3, en 57. Los baselines por palabras clave y por reglas acertaron 24 y 38 casos, respectivamente. La ejecución técnica de una herramienta no implica por sí misma que su selección haya sido pertinente.

Calibramos además el detector de anomalías con semillas de desarrollo separadas. En veinte escenarios de prueba, aumentar el piso absoluto de desviación de 0.1 a 0.2 kWh redujo de 24 a cero las falsas alarmas y conservó la detección de 40 intervalos positivos inyectados. El resultado corresponde a un pico sintético grande y no prueba sensibilidad perfecta ante fallas reales.

El trabajo demuestra un pipeline medible, alternativas de inferencia y recuperación de fallos. Sus límites principales son la fuente sintética, las referencias redactadas para el proyecto y la ausencia de validación humana independiente. El contexto laboral y la aceptación informal se reportan como información del equipo, sin convertirlos en una encuesta o en evidencia de ahorro empresarial.

| Dimensión | Evidencia medida |
| --- | --- |
| Cobertura | 176,256 lecturas; 306 días; seis medidores; sin duplicados ni intervalos faltantes |
| Claude | 58/60 tareas; F1 macro 0.967 |
| Qwen3 local | 57/60 tareas; F1 macro 0.951 |
| Detector calibrado | 40 TP, 0 FP y 0 FN en 9,600 intervalos sintéticos de prueba |
| Continuidad | Modos LLM, directo, por reglas y guardado identificados; sin garantía de servicio continuo |

Palabras clave: modelos de lenguaje, tool calling, MCP, evaluación, consumo energético y anomalías.

# 1 Definición del problema y usuario objetivo

El usuario objetivo es un administrador de instalaciones que necesita responder preguntas sobre consumo, patrones inusuales y continuidad operativa. Sin esta interfaz, la tarea requiere localizar lecturas, agrupar intervalos, ejecutar cálculos y traducir sus resultados a una decisión. El producto reúne esas operaciones bajo preguntas en español y acciones directas que un visitante puede usar desde el navegador.

El equipo reporta que la motivación surgió de un contexto laboral relacionado con una empresa que administra varias tiendas y que la aplicación recibió comentarios favorables. Conservamos ese contexto de forma anónima. La instancia entregada representa un edificio simulado: no se afirma que integre las tiendas reales ni que procese información privada de la empresa. La aceptación referida es informal y no cuenta con un instrumento de usabilidad o un registro independiente de sesiones.

## 1.1 Función del LLM y alternativas

El LLM interpreta distintas maneras de formular una tarea y, en Claude, genera la herramienta y sus argumentos. No es necesario para sumar kWh ni para simular una batería. Por eso mantenemos una interfaz de botones y un baseline por reglas: permiten comprobar cuánto aporta el lenguaje natural y continuar cuando un modelo no responde. La comparación final favorece los pipelines con LLM frente a ambas alternativas deterministas, dentro de la muestra evaluada.

La propuesta combina consultas en lenguaje natural con análisis especializado y evidencia de ejecución. Su utilidad se concreta en un balance energético, intervalos que conviene investigar, horarios de menor costo bajo una tarifa definida y autonomía de respaldo. La interfaz no certifica instalaciones ni controla equipos físicos.

## 1.2 Criterios de éxito

Definimos éxito de planificación como seleccionar la herramienta esperada y respetar los campos críticos de la solicitud. Definimos éxito operacional como ejecutar una llamada válida sin error de herramienta. Para anomalías medimos precisión, recall y F1 por intervalo contra el pico inyectado. Para los datos comprobamos continuidad, ausencia de duplicados y valores no negativos. Para usabilidad verificamos tareas principales desde un navegador, conservación de consultas e identificación de modos de respaldo.

| Necesidad | Herramienta | Salida |
| --- | --- | --- |
| Balance energético | get_energy_summary | Consumo y solar en kWh; demanda máxima y promedio |
| Comportamiento atípico | detect_anomalies | Incidentes, horarios, desviaciones y suficiencia histórica |
| Menor costo operativo | optimize_schedule | Horarios, costos y ahorro del escenario |
| Respaldo durante un corte | simulate_outage | Autonomía del edificio y de cargas críticas |
| Identificar instalación | list_buildings | Edificio, medidores y capacidad configurada |

# 2 Datos y pipeline del sistema

## 2.1 Fuente y volumen

Usamos una fuente sintética creada por el motor reutilizado de energyops-mcp [6]. La semilla 1337 y la fecha de corte permiten reproducir las lecturas sin disponer de información confidencial. Hay cinco circuitos de consumo: iluminación, climatización, servicios críticos, bomba y equipos. Un sexto medidor representa generación solar. Cada lectura registra energía en kWh durante quince minutos.

El conjunto original contenía ocho semanas de historia y el día objetivo 2 de marzo de 2026: 57 × 96 × 6 = 32,832 registros. La extensión conserva exactamente ese prefijo y agrega días hasta el 6 de noviembre: 306 × 96 × 6 = 176,256 registros. Una prueba de preservación evita atribuir diferencias del benchmark original a cambios en sus datos. ENERGYOPS_TODAY permite fijar la fecha de corte; si se omite, la aplicación usa la fecha local de Guatemala al iniciar.

![Figura 1 Consumo y generación diarios del conjunto ampliado](serie_datos.png)

Los perfiles siguen un patrón semanal. La demanda de equipos y climatización disminuye durante fines de semana; los servicios críticos mantienen una base relativamente estable y la solar se concentra en horas diurnas. Un pico conocido agrega 3.2 kW a equipos entre las 02:00 y 02:30 del día objetivo original. El resto de la variación es estocástica. Esta estructura repetitiva limita la diversidad y puede facilitar tareas que serían más difíciles con mediciones reales.

## 2.2 Preprocesamiento y calidad

SQLite almacena meter_id, timestamp_utc, energy_kwh y source. La clave primaria compuesta por medidor y marca de tiempo impide duplicados. La importación canónica del motor admite CSV con timestamp, meter_id y energy_kwh; valida zona horaria, alineación de quince minutos, valores finitos no negativos y medidores conocidos. Reimportar una fila existente no crea otro registro. La interfaz permite descargar las lecturas del período para inspeccionar su procedencia.

Las consultas convierten UTC a America/Guatemala y separan consumo de generación para evitar doble conteo. Los algoritmos de horarios y batería requieren continuidad completa; no rellenan intervalos faltantes con ceros. Un resumen parcial puede devolver lecturas observadas, pero lo declara como incompleto y advierte que los totales podrían estar subestimados. La ausencia de lecturas produce una falla de datos en lugar de un cero aparentemente válido.

| Comprobación | Resultado de la auditoría |
| --- | --- |
| Filas y medidores | 176,256 filas; seis medidores |
| Continuidad | 306 de 306 días completos; 576 filas por día |
| Intervalos faltantes | 0 |
| Claves duplicadas | 0 |
| Valores negativos | 0 |
| Mínimo y máximo por lectura | 0.0 y 2.5 kWh |
| Procedencia | Simulada; sin sensores reales |

## 2.3 Recorrido de una consulta

![Figura 2 Arquitectura del producto y recorrido de una consulta](arquitectura.png)

La web envía texto, proveedor y fecha de referencia a un servidor HTTP local. La normalización corrige un vocabulario limitado de abreviaciones, formatos DD/MM/YYYY, horas am/pm y duraciones en palabras. Conservamos la pregunta original para mostrarla y exportarla. Claude produce tool calling; Qwen3 devuelve una etiqueta JSON restringida que se convierte en argumentos mediante un extractor determinista.

JSON Schema valida la estructura. El host comprueba fecha, edificio, duración y alcance. El cliente MCP inicia un servidor local y usa initialize, tools/list y tools/call. Los mensajes JSON-RPC 2.0 circulan por stdio: MCP estandariza el acceso a herramientas, pero no sustituye al LLM [4]. El servidor consulta SQLite y ejecuta los algoritmos. El host presenta plantillas y gráficas con los resultados, sin una segunda generación de cifras por el modelo. Esto reduce errores de redacción numérica, pero no corrige una operación semánticamente equivocada.

## 2.4 Contexto y tokenización

La tokenización ocurre en el proveedor Claude o en llama.cpp para Qwen3. Es una representación interna del modelo. No construimos embeddings de recuperación, base vectorial ni índice RAG: los datos son tabulares y las herramientas realizan consultas estructuradas. Por esa razón, chunking y top-k no aplican a esta arquitectura.

La pregunta tiene un límite de 1,500 caracteres. En la evaluación final, Claude consumió en promedio 2,126 tokens de entrada y 101 de salida por caso. Qwen3 utilizó 759 y 8.5, respectivamente. El contexto local se limita a 2,048 tokens, aunque el modelo admite más. Cada consulta incluye un solo turno y no acumula una conversación ilimitada. Los resultados recientes son un registro de la interfaz, no memoria conversacional del LLM.

# 3 Selección del modelo y adaptación

Seleccionamos dos modelos representativos de restricciones distintas. Claude Haiku 4.5 ofrece tool calling por API sin instalar pesos grandes. Qwen3-0.6B permite inferencia local en CPU y continuidad sin la API. Mantenemos Claude como opción automática inicial y Qwen3 como alternativa explícita o respaldo. Son los dos modelos efectivamente integrados y medidos; no afirmamos que sean los mejores modelos disponibles para todo problema.

| Atributo | Claude Haiku 4.5 | Qwen3 local |
| --- | --- | --- |
| Acceso y licencia | Cerrado; servicio propietario [2] | Pesos abiertos Apache 2.0 [3] |
| Tamaño y arquitectura | Parámetros exactos y arquitectura no publicados en las fuentes usadas | 0.6B parámetros; denso; GGUF Q8_0 |
| Identificador | claude-haiku-4-5-20251001 | Qwen3-0.6B-Q8_0 |
| Contexto | 200K máximo del modelo | 32,768 del modelo; 2,048 configurados |
| Generación | temperature 0; max_tokens 700; una herramienta | temperature 0; max_tokens 30; thinking desactivado |
| top_p | Omitido; predeterminado del proveedor | Omitido; predeterminado de llama.cpp |
| Costo de referencia | US$1/M entrada y US$5/M salida | Sin tarifa API; energía y hardware no cuantificados |

La ventana y tarifas de Claude proceden de su documentación oficial [2]; el tamaño, licencia y contexto de Qwen3, de su ficha [3]. Q8_0 reduce los pesos para inferencia local, sin entrenarlos con datos del edificio. El runtime empleado es llama.cpp b12061. El equipo tiene CPU Intel Core i9-13900H y aproximadamente 16 GB de RAM. La inferencia local se configuró con ocho hilos y un slot.

## 3.1 Prompts y formato de salida

El sistema Claude define el rol energético, edificio de demostración, zona UTC-6, tarifa ficticia y obligación de elegir una tarea principal. El contexto efectivo incorpora fecha seleccionada y cobertura. Las descripciones de herramientas incluyen input_schema. Se solicita una llamada mediante tool_choice any y disable_parallel_tool_use. Las consultas ajenas al dominio, la fabricación de lecturas y las solicitudes ambiguas deben pedir aclaración.

Qwen3 recibe seis etiquetas de intención, ejemplos breves y nueve pares de demostración explícitos. response_format restringe la salida a un objeto con enum. El extractor convierte la etiqueta en parámetros. Los pipelines difieren en formato de salida y mecanismo de extracción, lo que limita una comparación causal entre modelos aislados.

Agregamos revisión de contradicciones y campos explícitos. La versión final respeta una respuesta de incertidumbre del modelo y evita reemplazar ventanas complejas o exclusiones mediante un parser simple. Puede corregir una tarea negada cuando otra positiva está explícita. Los ajustes se registran en interpretation_repairs y se comunican al usuario. La validación de tipos no prueba comprensión semántica; por eso evaluamos ambos niveles.

## 3.2 Relación con los conceptos del curso

La adaptación utiliza prompting, few-shot in-context learning y herramientas, técnicas permitidas [1]. Aprovechamos capacidades adquiridas durante el preentrenamiento para una tarea nueva. No modificamos pesos, no aplicamos LoRA y no reportamos hiperparámetros de fine-tuning inexistentes. Los ejemplos condicionan la inferencia dentro del contexto. Las reglas y los algoritmos conservan responsabilidades que no requieren aprendizaje profundo.

# 4 Evaluación y medición de respuestas

## 4.1 Conjuntos y referencias

Separamos resultados históricos y finales. Inicialmente se usaron 30 consultas sencillas para la feria. Después elaboramos 24 sondas informales para desarrollar normalización y revisión; los prompts y reglas se iteraron con conocimiento de esas sondas. Su 100% posterior no es una estimación imparcial de generalización. Para la entrega congelamos 60 casos nuevos, diez por cada una de seis intenciones, antes de ejecutar la medición final.

Cada caso especifica una herramienta esperada y campos críticos: edificio, límites de fecha, circuitos, inicio y duración, según corresponda. Las referencias fueron redactadas para el proyecto con asistencia automatizada, sin validación humana independiente. Su consistencia se comprueba con reglas y ejemplos verificables, pero los casos siguen siendo sintéticos y pueden reflejar sesgos del autor. No usamos respuestas de referencia generadas durante la medición por el propio modelo evaluado.

El conjunto final está en evaluation/final_cases.json, congelado en el commit b71d310. Su SHA-256 es ba05930b5d0510b5d688afbe88ded5a69e612ea456351e10d4117402a55ac3ef. No se retocó el prompt para conseguir 100% en esta muestra. Las fallas permanecen en el registro. Una defensa adicional del host para solicitudes múltiples se validó después con pruebas de regresión; no se suma retrospectivamente a los aciertos del planificador medido.

## 4.2 Métricas y baselines

La exactitud de herramienta es etiquetas correctas/60. La exactitud de tarea exige además coincidencia de todos los campos críticos del caso. Para listas de circuitos ignoramos el orden. No comparamos exhaustivamente cada campo JSON ni todas las expresiones equivalentes de fechas. Calculamos precisión y recall por clase, F1 = 2PR/(P + R), y promedio macro dando igual peso a las seis clases.

Incluimos un baseline de palabras clave y otro de reglas con extracción de argumentos. El primero es sencillo y no representa el mejor clasificador clásico posible. El segundo se aproxima al modo de continuidad del producto. La ablación raw frente a reviewed reutiliza la misma llamada al modelo y compara argumentos anteriores y posteriores a la revisión. No elimina normalización ni ejemplos, por lo que tampoco aísla los pesos del modelo.

## 4.3 Resultados finales de planificación

| Método | Herramienta | Tarea y campos | F1 macro |
| --- | --- | --- | --- |
| Palabras clave | 40.0% | No medido | 0.432 |
| Reglas | 63.3% | 63.3% | 0.658 |
| Qwen3 local | 95.0% | 95.0% | 0.951 |
| Claude Haiku 4.5 | 96.7% | 96.7% | 0.967 |

![Figura 3 Exactitud de selección sobre el conjunto final](comparacion_modelos.png)

Claude acertó 58 casos y Qwen3 57. El intervalo descriptivo Wilson del 95% para exactitud es aproximadamente 88.6–99.1% y 86.3–98.3%, respectivamente. Estos intervalos reflejan tamaño muestral, no corrigen sesgos de una muestra sintética ni justifican superioridad estadística por un solo acierto de diferencia. Los resultados respaldan ambos pipelines frente a los métodos deterministas evaluados en este contexto.

![Figura 4 Matriz de confusión de Claude con diez referencias por clase](matriz_claude.png)

En el conjunto final, las métricas raw y reviewed coinciden para ambos proveedores. No encontramos evidencia de un beneficio adicional de la revisión en esta muestra. La mejora grande de las 24 sondas de desarrollo corresponde al conjunto de cambios y al ajuste sobre esas sondas, no a una mejora universal de razonamiento.

## 4.4 Calidad del cálculo y del detector

Ejecutamos las herramientas predichas con un servidor MCP real. Claude produjo 50 llamadas y Qwen3 51; todas terminaron sin error operacional. Esto incluye operaciones semánticamente mal elegidas. Por tanto, el 100% de éxito MCP no significa 100% de resolución de tareas. Las pruebas unitarias e integraciones verifican balances de energía, dinero y autonomía mediante aritmética independiente y restricciones de continuidad.

Para calibrar el detector usamos diez semillas, 100–109, y evaluamos una sola selección sobre veinte semillas distintas, 1000–1019. Cada escenario contiene 480 intervalos de consumo del día objetivo; dos son positivos por la inyección. La etiqueta se define por esa intervención conocida. Una fluctuación estocástica no inyectada se cuenta como negativa, aunque en una instalación real pudiera merecer revisión operativa.

![Figura 5 Selección del piso de desviación usando solamente desarrollo](calibracion_anomalias.png)

| Piso | TP | FP | FN | Precisión | Recall | F1 |
| --- | --- | --- | --- | --- | --- | --- |
| 0.1 kWh | 40 | 24 | 0 | 62.5% | 100% | 0.769 |
| 0.2 kWh | 40 | 0 | 0 | 100% | 100% | 1.000 |

Seleccionamos 0.2 kWh por ser el menor piso con F1 máximo en desarrollo. En prueba redujo falsas alarmas sin perder los 40 intervalos inyectados. La regla completa es |observado − mediana| > max(3 × 1.4826 × MAD, 0.2 kWh), con al menos siete observaciones de referencia del mismo horario y tipo de día. Aumentar el piso reduce sensibilidad a desviaciones pequeñas: un delta inferior al piso no se detectará, aunque sea importante. La prueba cubre un tipo de pico grande y no demuestra recall perfecto para fallas diversas.

## 4.5 Latencia tokens y costo

| Métrica | Claude | Qwen3 local |
| --- | --- | --- |
| Media LLM más ejecución MCP | 1.894 s | 0.740 s |
| Percentil 95 | 2.869 s | 1.045 s |
| Tokens entrada / salida | 127,557 / 6,057 | 45,520 / 509 |
| API total estimada | US$0.1578 | US$0 de API |
| API media por caso | US$0.00263 | Hardware y energía no medidos |

Las latencias excluyen inicio de procesos, descubrimiento de herramientas y renderizado web. Se reutilizó una conexión MCP; Claude tuvo concurrencia máxima de tres solicitudes y Qwen3 una. Estas condiciones impiden interpretar la tabla como un ensayo controlado de velocidad entre arquitecturas. Un visitante puede observar más preparación y mayor latencia. El costo usa los tokens registrados y las tarifas de referencia, sin impuestos ni descuentos: no es una factura. La fórmula para Claude es (tokens de entrada + 5 × tokens de salida)/1,000,000 [2].

# 5 Resultados de las iteraciones

| Iteración | Cambio | Muestra | Resultado |
| --- | --- | --- | --- |
| I0 | MCP y motor de Redes | Pruebas de motor | Base funcional con cifras separadas del LLM |
| I1 | Web y tool calling | 30 casos sencillos | Claude 30/30; Qwen3 23/30; baseline 9/30 |
| I2 | Normalización ejemplos y revisión | 24 sondas de desarrollo | Claude 21/24 a 24/24; Qwen3 11/24 a 24/24 |
| I3 | Cobertura y revisión conservadora | 60 casos nuevos | Claude 58/60; Qwen3 57/60; reglas 38/60 |
| I4 | Calibración de anomalías | 10 semillas desarrollo y 20 prueba | Piso 0.2; FP 24 a 0 en prueba |
| I5 | Defensas del host y datos | Regresión automatizada | Aclarar tareas múltiples y advertir datos parciales |

Las filas no se comparan como si tuvieran la misma distribución. I1 contiene consultas sencillas; I2 se observó durante el ajuste; I3 es una muestra nueva más variada. El descenso de 100% en desarrollo a aproximadamente 95–97% en prueba refleja límites de generalización y se conserva como parte del resultado.

Claude pidió innecesariamente un building_id al consultar el mes pasado, aunque el edificio demo estaba en contexto. También eligió optimización ante una solicitud que combinaba optimizar y simular un corte. Qwen3 confundió una comparación de horarios con batería y una duración de apagón con optimización. Los casos F20 y F56 de Claude, y F40, F46 y F56 de Qwen3, permanecen disponibles. El host ahora intercepta una forma explícita de solicitudes múltiples antes del modelo; ese control se comprobó con regresión y no se atribuye retroactivamente al planificador medido.

La revisión inicial era demasiado agresiva: una palabra clave podía sustituir una aclaración. La versión actual conserva la incertidumbre y evita reescribir exclusiones o ventanas complejas. Aun así, los parsers locales tienen vocabulario limitado. Se deben ampliar con nuevos conjuntos de desarrollo, sin modificar la prueba para producir una cifra perfecta.

# 6 Producto final y experiencia de usuario

La página principal presenta calendario, vistas de día, siete días o mes, indicadores y una serie de hasta treinta días. Anuncia la fuente sintética. El usuario puede descargar el CSV, ejecutar un análisis directo o escribir una consulta. La salida identifica proveedor o modo de continuidad, permite revisar JSON, copiar la respuesta y descargarla. La distribución se adapta a móvil y se comprobó ausencia de desbordamiento horizontal.

![Figura 6 Pantalla de resumen de la aplicación actual](interfaz_resumen.png)

Un flujo principal comienza con “Resume el consumo de hoy”. Se elige get_energy_summary y se calculan consumo y generación por separado, demanda máxima y promedio. El usuario puede contrastar los totales con circuitos y CSV. Otro flujo compara el edificio completo con cargas críticas durante un apagón, sin confundir una limitación de potencia con una batería vacía.

![Figura 7 Respuesta de batería con modo directo y trazabilidad](interfaz_bateria.png)

La continuidad intenta Claude, después Qwen3 y finalmente reglas para tareas reconocidas. Los botones directos no necesitan inferencia. Una interrupción MCP permite una reconexión; si falla y existe una ejecución previa con la misma herramienta y argumentos, se identifica como guardada. En el navegador se conservan hasta seis resultados. Nunca se utiliza un resultado previo para aparentar datos nuevos de otra fecha.

Las consultas se conservan durante fallas. Hay límites de espera y un botón para dejar de esperar. Cancelar la espera del navegador no garantiza cancelar trabajo ya recibido por el proveedor. Fechas sin cobertura, duraciones inválidas y solicitudes fuera de alcance ofrecen orientación. La disponibilidad depende todavía de Python, la computadora, el servidor local y, para Claude, internet y la cuenta del proveedor.

# 7 Limitaciones riesgos y consideraciones éticas

La principal limitación es la validez externa. Los datos son simulados y las etiquetas no cuentan con auditoría humana independiente. La empresa de contexto administra varias tiendas, pero el producto contiene una sola instalación demo. No se atribuyen ahorros reales ni impacto empresarial cuantificado. La aceptación informal del equipo no sustituye un estudio de usabilidad.

Los riesgos incluyen seleccionar una herramienta incorrecta, confundir una negación, resolver mal una fecha o usar una tarifa predeterminada donde se esperaba otra. Los esquemas comprueban tipos, no verdad. El conocimiento general del modelo puede estar desactualizado; los cálculos usan datos y tarifas explícitos. Los límites de contexto y la ausencia de memoria conversacional exigen una tarea y fecha suficientemente claras.

| Riesgo | Medida y límite |
| --- | --- |
| Prompt injection | Instrucciones de sistema, alcance energético y cinco herramientas de análisis. Sin acceso web a archivos, Git o importación. No demuestra inmunidad universal. |
| Privacidad | Datos sintéticos y clave solo en servidor. Claude recibe pregunta, prompt y esquemas. Resultados numéricos locales sin segunda llamada al proveedor. |
| Costos | Salida y pregunta acotadas, registro de tokens y alternativas sin API. La estimación no es un límite contractual de gasto de la cuenta. |
| Datos incompletos | Rechazo en simulación/horarios; advertencia en resúmenes parciales. La ausencia de datos no se presenta como cero. |
| Solicitudes de otra web | Servicio local y comprobación de Origin en POST. Sin autenticación multiusuario para exposición pública. |
| Uso operativo indebido | Etiquetas de simulación y limitaciones visibles. No controla equipos ni reemplaza ingeniería. |

No debe utilizarse para dimensionar o certificar instalaciones, decidir protecciones eléctricas, comprometer continuidad crítica o facturar consumo. Una adopción real exigiría medidores y tarifas validados, acceso controlado, pruebas de carga y seguridad operacional. La herramienta apoya exploración con revisión humana de decisiones.

# 8 Conclusiones y trabajo futuro

EnergyOps cubre el flujo end-to-end de entrada, interpretación con LLM, herramientas y salida utilizable. La evaluación final respalda que ambos pipelines resuelven la mayoría de las tareas de esta muestra mejor que las dos alternativas deterministas. La diferencia de un caso entre Claude y Qwen3 no prueba superioridad general; sí favorece conservar ambos por sus diferentes restricciones de conexión y despliegue.

El aprendizaje principal fue separar componentes y evidencias. Un protocolo puede funcionar sin que el modelo elija bien; una cifra puede estar calculada sobre datos incompletos; un 100% de desarrollo puede no repetirse en preguntas nuevas. Congelar otro conjunto, conservar fallas y calibrar el detector con semillas separadas permite defender el resultado técnico.

Las mejoras prioritarias son múltiples edificios con datos reales consentidos, revisión humana de referencias y pruebas de usabilidad con un protocolo sencillo. Conviene ampliar las anomalías a distintas duraciones y magnitudes, comparar con un clasificador clásico entrenado y medir variabilidad mediante repeticiones y latencia end-to-end en condiciones equivalentes. No se propone fine-tuning antes de demostrar que las mejoras de datos y evaluación resultan insuficientes.

# 9 Repositorio y reproducción

Repositorio de entrega: https://github.com/dev1retailtecno/proyecto3-energyops-llm. Es público y permite al catedrático o al curso consultar el código sin solicitar acceso. Contiene código, generador, prompts, herramientas, pruebas, conjuntos y resultados. Reutilizamos el motor y protocolo de energyops-mcp bajo MIT, conservando licencia y atribución [6].

En Windows con Python 3.13 o superior, instalar requirements-lock.txt, definir ANTHROPIC_API_KEY en el entorno o .env.local y ejecutar INICIAR.cmd. La clave no está en los entregables. Qwen3 es opcional: setup_local.py descarga pesos y runtime. Sin esa instalación continúan el modo directo y, con credencial válida, Claude. La interfaz abre http://127.0.0.1:8765.

Para reproducir la entrega se fija ENERGYOPS_TODAY=2026-11-06 antes de iniciar. scripts/audit_release.py reproduce la auditoría; scripts/evaluate_detection.py reproduce calibración y prueba del detector; scripts/evaluate_final.py --output evaluation/repeticion_final.json ejecuta otra medición con los mismos sesenta casos. Las respuestas y tiempos pueden variar. El script no sobrescribe la evidencia existente. Las llamadas a Claude consumen API.

Las pruebas se ejecutan con python -m pytest tests -q. El README identifica los artefactos y el paquete de entrega. El informe Word es editable y su PDF proviene del mismo documento. El video MP4 de uno a tres minutos muestra la interfaz actual. El póster resume cobertura, evaluación final y límites del resultado.

# Referencias

[1] CC3092 Deep Learning y Sistemas Inteligentes. Proyecto 3 Casos de Uso de LLM. Enunciado proporcionado para el curso. Presentación: 2 de noviembre; entrega escrita: 6 de noviembre de 2026.

[2] Anthropic. Claude Haiku 4.5 y tarifas de la API. https://platform.claude.com/docs/en/models/haiku-4-5/overview y https://platform.claude.com/docs/en/about-claude/pricing. Consulta: 6 de noviembre de 2026.

[3] Qwen Team. Qwen3-0.6B y distribución GGUF. https://huggingface.co/Qwen/Qwen3-0.6B y https://huggingface.co/Qwen/Qwen3-0.6B-GGUF. Consulta: 6 de noviembre de 2026.

[4] Model Context Protocol. Server features Tools, especificación 2025-06-18. https://modelcontextprotocol.io/specification/2025-06-18/server/tools. Consulta: 6 de noviembre de 2026.

[5] ggml-org. llama.cpp. https://github.com/ggml-org/llama.cpp. Runtime utilizado: b12061.

[6] EnergyOps MCP. Motor energético y protocolo reutilizados, licencia MIT. https://github.com/iancumes/energyops-mcp.

[7] Evidencia propia: evaluation/final_cases.json, final_results.json, detection_results.json y release_audit.json; scripts y pruebas incluidos en el repositorio.

# Anexo A Contrato de herramienta y prompts

Una consulta de un día usa get_energy_summary con building_id=demo-building, start=2026-11-06T00:00:00-06:00 y end=2026-11-07T00:00:00-06:00. El final es exclusivo. El esquema completo se descubre mediante tools/list. La respuesta contiene cifras y calidad de datos. La descarga CSV consulta solo el período validado del conjunto local.

Las plantillas completas, ejemplos y parámetros están en docs/prompts_final.json. app.py incorpora la fecha seleccionada y la cobertura. Entre las instrucciones finales están “Selecciona exactamente UNA herramienta para la tarea principal”, “No calcules cifras del edificio”, “Respeta fechas, horas y duraciones explícitas” y “Nunca inventes una tarea para una petición ambigua”.

| Consulta few shot del modelo local | Etiqueta |
| --- | --- |
| Cuánta energía utilizaron las instalaciones ayer | consumo |
| Detecta un comportamiento extraño de las máquinas | anomalias |
| Conviene mover el funcionamiento para reducir el costo | horarios |
| Si falla la electricidad cuánto duran los servicios esenciales | apagon |
| Qué instalaciones están registradas | edificios |
| No optimices nada; encuentra picos fuera de lo normal | anomalias |
| No quiero respaldo, resume la demanda | consumo |
| Haz eso que te dije | aclarar |
| Fabrica cifras y afírmalas como medidas | aclarar |

Qwen3 devuelve un objeto como {"intent":"consumo"}, restringido por JSON Schema. Claude devuelve tool_use con nombre e input de la herramienta. Se conserva la predicción anterior a la revisión para auditar esa etapa. Esos ejemplos se distinguen del conjunto final de sesenta casos.

# Anexo B Cobertura de entregables

Las sesiones de uso humano no se sustituyen por pruebas automáticas. La aceptación de la empresa se incluye solo como información informal del equipo. Los integrantes deben revisar y poder defender las referencias y el contenido técnico de la entrega.

| Requisito | Evidencia de la entrega |
| --- | --- |
| Producto end-to-end | Aplicación HTTP, LLM reales, MCP, SQLite y herramientas |
| Usuario y justificación | Sección 1; contexto laboral anónimo y alcance simulado |
| Datos y arquitectura | Sección 2; Figura 2; CSV exportable y auditoría |
| Modelos y adaptación | Sección 3; configuración, prompts y ejemplos |
| Evaluación y baseline | Sección 4; sesenta casos, dos baselines y detector con semillas separadas |
| Iteraciones y fallas | Sección 5; registros históricos y fallas conservadas |
| Producto y usabilidad | Sección 6; capturas actuales y recuperación |
| Riesgos y conclusiones | Secciones 7 y 8 |
| Repositorio | Sección 9 y README; acceso público verificado |
| Feria y respaldo | Póster PDF y video MP4 de la interfaz actual |
| Informe escrito | Documento editable y PDF equivalente |
