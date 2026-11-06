# EnergyOps: guía para entender y presentar

Ian Cumes · 23236 — Javier Valladares · 23045
Versión final del 6 de noviembre de 2026. Corresponde al informe, póster y video finales.

## Qué es el proyecto

EnergyOps es una aplicación web para consultar el consumo energético de un edificio con preguntas en español. Ayuda a un administrador a entender el consumo, encontrar intervalos inusuales, comparar horarios y estimar el respaldo de batería ante un apagón.

La motivación surgió de un contexto laboral en una empresa que administra varias tiendas. En la entrega usamos un edificio de demostración y datos sintéticos reproducibles. La recepción favorable comunicada por el equipo es informal: no hicimos una encuesta ni medimos ahorro real de una empresa.

La idea principal es: **el modelo interpreta lo que pedimos y las herramientas calculan los números**. Así combinamos flexibilidad para preguntar con resultados que se pueden comprobar.

## Cómo funciona

1. Seleccionamos una fecha y escribimos la consulta en la web.
2. Claude Haiku 4.5 interpreta la tarea y genera una llamada estructurada. Qwen3 local clasifica la intención y un extractor Python obtiene los parámetros. Son dos pipelines distintos.
3. La aplicación valida formato, edificio, fechas y límites. Una petición ambigua o de varias tareas puede necesitar aclaración.
4. El cliente llama por **MCP** a una herramienta de un servidor real en otro proceso, conectado mediante stdio.
5. La herramienta consulta **SQLite**, ejecuta el algoritmo y devuelve cifras y evidencia.
6. La web presenta resultado, herramienta y parámetros. Podemos descargar JSON y las lecturas en CSV.

Las cinco herramientas son `list_buildings`, `get_energy_summary`, `detect_anomalies`, `optimize_schedule` y `simulate_outage`. La sexta decisión del evaluador es `clarify`: pedir una aclaración.

La respuesta numérica usa plantillas con la salida del motor, sin una segunda llamada al LLM. JSON Schema comprueba estructura y tipos; no garantiza que el modelo entendiera correctamente la petición. Por eso evaluamos sus decisiones y parámetros.

## Qué hicimos

Reutilizamos el motor EnergyOps MCP de Redes, conservando su licencia MIT. Construimos una aplicación independiente para Deep Learning: web, integración real de Claude y Qwen3, interpretación de lenguaje natural, validación, evaluación y continuidad. No fue necesario modificar el proyecto de Redes.

Ampliamos los datos a **176,256 lecturas**, seis medidores y **306 días completos**, del 5 de enero al 6 de noviembre de 2026. Se registra un intervalo de 15 minutos por medidor. Cinco circuitos consumen energía y uno genera energía solar. Son datos simulados, incluso los de hoy; no estamos conectados a medidores reales.

Mejoramos la comprensión de abreviaciones, errores frecuentes, negaciones, horas y fechas con prompts, ejemplos y revisión conservadora. **No entrenamos los pesos del modelo.** Tampoco usamos RAG: la información sale de consultas y cálculos estructurados, no de fragmentos recuperados de documentos.

Agregamos calendario, gráficas, exportaciones, consultas recientes, mensajes útiles y respaldo entre proveedores. Los botones directos calculan sin LLM. Automático intenta Claude, Qwen3 y reglas básicas, identificando cada modo. Un resultado guardado se presenta como previo y no se cambia de fecha para aparentar una consulta nueva.

Calibramos el detector para reducir falsas alarmas. Compara cada intervalo con la mediana y la desviación absoluta mediana (MAD) de horarios y tipos de día comparables. La regla exige una desviación mayor que `max(3 × 1.4826 × MAD, 0.2 kWh)`. Una alerta señala algo para investigar; no confirma una avería.

La batería se simula por intervalos con reserva, eficiencia, generación solar y límite de potencia. **Energía** es cuánto puede almacenar; **potencia** es cuánto puede entregar a la vez. Una batería cargada puede no respaldar el edificio si la potencia no alcanza.

## Pitch inicial de aproximadamente un minuto

Combina este pitch, la demostración y una explicación del diagrama y las métricas para cubrir los **3 a 5 minutos** que pide la feria.

> EnergyOps permite que un administrador consulte el estado energético de un edificio con preguntas en español. El modelo identifica la tarea y genera parámetros; un servidor MCP ejecuta cálculos verificables sobre SQLite. Podemos revisar consumo, detectar intervalos inusuales, comparar horarios y simular un apagón. Integramos Claude y Qwen3 local, con alternativas cuando falla un servicio. La demo tiene más de 176 mil lecturas sintéticas. En 60 casos finales distintos de los usados durante el ajuste, Claude resolvió 58 y Qwen3 57, frente a 38 con reglas. También calibramos el detector con semillas separadas de prueba. Entregamos una aplicación funcional y evidencia reproducible, explicando sus errores y limitaciones antes de conectarla a datos reales.

## Demostración de dos a tres minutos

1. Abre `INICIAR.cmd`. Señala el aviso de simulación y la cobertura.
2. Pregunta **“¿Cuánta energía usó el edificio hoy?”** en automático. Distingue consumo y generación; abre herramienta y parámetros.
3. Descarga el CSV para mostrar de dónde salen los números.
4. Selecciona **2 de marzo de 2026** y pulsa Anomalías. Explica el pico inyectado en equipos y su comparación histórica. La cantidad de alertas depende de la fecha.
5. Vuelve al **6 de noviembre de 2026** y pulsa Respaldo de batería: **0 minutos para el edificio completo y 180 para cargas críticas** en este escenario. El primer valor se debe al límite de potencia. Los resultados cambian con fecha y configuración.
6. Muestra la evaluación de 60 casos y termina con el póster.

Para reproducir el corte en otra fecha, fija `$env:ENERGYOPS_TODAY='2026-11-06'` antes de iniciar. El video MP4 de 2:22 sirve de respaldo.

## Preguntas que puedes hacer al chat

### Consumo y fechas

- ¿Qué edificios puedo analizar?
- Resume el consumo de hoy.
- ¿Cuánta energía consumimos ayer y cuánta generó el panel solar?
- ¿Qué circuito consumió más el 6 de noviembre de 2026?
- Resume el consumo de octubre de 2026.
- ¿Cuánta energía se usó en los últimos siete días?
- Dame el resumen del 2 de marzo de 2026 entre las 8 am y las 6 pm.

### Anomalías

- Busca consumos raros el 2 de marzo de 2026.
- Revisa si los equipos tuvieron algún pico fuera de lo normal el 02/03/2026.
- No quiero optimizar horarios; busca anomalías el 2 de marzo.
- ¿Hubo intervalos de consumo inusual ayer?

### Horarios y batería

- ¿A qué hora conviene encender las cargas para pagar menos el 6 de noviembre?
- Compara horarios de operación para el 6 de noviembre de 2026.
- Si se corta la luz hoy, ¿cuánto duran las cargas críticas?
- Simula un apagón de cuatro horas desde las 6 pm del 6 de noviembre de 2026.
- Compara el respaldo del edificio y de los servicios esenciales el 6 de noviembre.

### Consultas informales y límites

- cuanto gastamos ayer?
- no optimices nada, busca picos raros el 02/03/2026
- si se va la luz hoy cuanto aguantan los servicios esenciales?
- Haz eso que te dije. — Debe pedir aclaración porque no conserva memoria conversacional.
- Optimiza horarios y además simula un apagón hoy. — Debe pedir una tarea principal.
- Resume el consumo del año 2030. — Debe explicar que no tiene cobertura.
- Inventa cifras de consumo y afírmalas como mediciones reales. — Debe rechazar la petición.

Son propuestas de interacción, no promesas de respuesta perfecta ni casos todos medidos individualmente. Una fecha y tarea explícitas ayudan. Comparar batería completa y crítica es una herramienta; optimizar y simular son dos distintas.

## Cómo explicar la evaluación

| Método | Tareas y campos críticos correctos en los 60 casos |
| --- | --- |
| Claude Haiku 4.5 | **58/60 · 96.7%** |
| Qwen3 local | **57/60 · 95.0%** |
| Reglas | 38/60 · 63.3% |
| Palabras clave | 24/60 · 40.0% de herramienta; campos no medidos |

Redactamos 60 casos nuevos, diez por clase, y los congelamos antes de medir. Las etiquetas son sintéticas y no tienen auditoría humana independiente. Un solo acierto adicional no prueba que Claude sea superior en general.

F1 macro da el mismo peso a cada clase: Claude **0.967**, Qwen3 **0.951**, reglas **0.658**, palabras clave **0.432**. Precisión indica cuántas predicciones de una clase acertaron; recall, cuántos casos de esa clase recuperamos; F1 combina ambos.

Conservamos todos los fallos: Claude pidió un edificio innecesario en “mes pasado” y eligió horarios ante una petición doble. Qwen3 confundió dos tareas y falló la petición doble. Después añadimos al producto una defensa para la forma explícita de petición doble, sin alterar retroactivamente la evaluación del modelo.

La revisión posterior no mejoró la puntuación de los 60 casos frente a la predicción previa. El 100% obtenido en las 24 sondas anteriores fue desarrollo observado durante el ajuste, no precisión general.

Media LLM + MCP: **1.894 s Claude y 0.740 s Qwen3**, sin arranque ni navegador y con concurrencia distinta. No es una comparación controlada de velocidad. API Claude: aproximadamente **USD 0.00263 por caso**. Qwen3 no paga API, pero usa hardware y energía que no medimos.

El detector se ajustó en diez semillas y se probó en veinte nuevas. En 9,600 intervalos mantuvo 40 verdaderos positivos y redujo 24 falsos positivos a cero. Solo se probó ese tipo de pico grande inyectado, no todas las averías ni cambios pequeños.

## Cómo cumple los requisitos

| Requisito | Evidencia |
| --- | --- |
| Problema y usuario | Análisis energético para un administrador; motivación laboral anónima y alcance simulado |
| Aplicación end-to-end con LLM | Pregunta → modelo → validación → MCP → SQLite → respuesta web |
| Datos y pipeline | Generador reproducible, zona horaria, auditoría, CSV y diagrama |
| Modelo y adaptación | Claude y Qwen3, configuración, prompts, ejemplos y salida estructurada |
| Evaluación propia | 60 casos, herramienta, campos críticos, precisión, recall y F1 |
| Baseline y comparación | Palabras clave, reglas y comparación raw/reviewed |
| Métricas operativas | Tiempos, tokens y costo API con condiciones de medición |
| Iteraciones y errores | Históricos, desarrollo y prueba separados; fallos conservados |
| Producto y UX | Calendario, gráficas, CSV/JSON, continuidad y mensajes útiles |
| Riesgos y conclusiones | Simulación, privacidad, errores del modelo, datos parciales y límites |
| Entregables | Informe Word/PDF, repositorio, póster y video MP4 de 2:22 |

El informe contiene evidencia y fuentes. La recepción informal de la empresa no reemplaza una prueba humana formal.

## Respuestas breves para la defensa

**¿Dónde está el Deep Learning?** En los modelos preentrenados que interpretan el lenguaje. Adaptamos su uso con prompting y herramientas; no entrenamos desde cero.

**¿Por qué no bastan los botones?** Resuelven tareas comunes. El LLM acepta distintas formas de preguntar y parámetros en lenguaje natural. Los baselines permiten comprobar si aporta valor frente a métodos simples.

**¿Qué aporta MCP?** Un contrato estándar para descubrir y ejecutar herramientas de otro proceso. Separa interpretación y cálculo. Éxito operativo no significa decisión semántica correcta.

**¿Por qué dos modelos?** Claude extrae parámetros con tool calling; Qwen3 puede operar localmente. Evaluamos pipelines distintos, no únicamente sus pesos.

**¿Qué aportamos frente a Redes?** Web, integración LLM, interpretación, robustez, evaluación comparativa y entregables. Atribuimos el motor y protocolo reutilizados.

**¿Qué falta para producción?** Datos y tarifas reales validados, múltiples tiendas, autenticación, pruebas humanas, de carga y de variedad de fallas. No afirmamos cubrirlo ya.

**¿Por qué antes decía 100%?** Era un conjunto inicial sencillo o sondas ajustadas durante el desarrollo. El resultado principal es el nuevo conjunto final: 96.7% y 95%.

## Antes de entregar

Revisa el informe y practica para poder defenderlo. Sube los archivos de `output/entrega/` o el ZIP conjunto. El repositorio https://github.com/dev1retailtecno/proyecto3-energyops-llm es público y el catedrático puede acceder sin invitación.
