# Solución Prueba de Diagnóstico - Ingeniería de Datos

A continuación, presento la documentación de mi solución para la prueba, detallando las decisiones de diseño que tomé para abordar el problema y las instrucciones paso a paso para ejecutar el sistema en cualquier equipo.

---

##  Arquitectura y Decisiones de Diseño

### 1. Separación de componentes (Miner y Visualizer)
La separación se implementó utilizando Python para el `miner` y Node.js para el `visualizer`.
* **Justificación técnica:** Python se seleccionó por su soporte nativo de análisis de sintaxis (`ast`) y manejo de peticiones asíncronas. Node.js se utilizó para la gestión de flujos de datos (streams) y la entrega de eventos en tiempo real al navegador.

### 2. Comunicación mediante Volumen Compartido
Se utilizó un volumen compartido de Docker con un archivo en formato `jsonl` para el intercambio de datos entre servicios.
* **Justificación técnica:** Este método evita la latencia y el consumo de recursos de una base de datos tradicional. Permite una escritura secuencial rápida por parte del productor y una lectura de deltas por parte del consumidor, funcionando como un log de eventos.

### 3. Extracción selectiva de código
El sistema no clona los repositorios. Utiliza la API de GitHub para obtener la estructura de archivos y descarga únicamente el contenido de los archivos con extensión `.py` y `.java`.
* **Justificación técnica:** Esta estrategia reduce el uso de ancho de banda y almacenamiento al omitir archivos no relevantes para el análisis solicitado.

### 4. Tolerancia a fallos y manejo de errores
Se implementaron reintentos con espera exponencial para gestionar los límites de la API de GitHub.
* **Justificación técnica:** El sistema gestiona excepciones de codificación (Unicode) y errores de red a nivel de archivo. Si un archivo falla, el proceso lo descarta y continúa con el resto del repositorio para evitar interrupciones en el flujo de datos.

### 5. Visualización mediante Server-Sent Events (SSE)
La comunicación entre el servidor Node.js y el cliente web se realiza mediante SSE.
* **Justificación técnica:** Al ser una comunicación unidireccional de datos en tiempo real, SSE es más eficiente y simple de implementar que WebSockets, eliminando la necesidad de librerías externas en el frontend.

---

##  Instrucciones de Ejecución

### Requisitos Previos
* Tener **Docker** y **Docker Compose** instalados.
* Contar con un Token de Acceso Personal (PAT) clásico de GitHub.

### Paso 1: Configurar la credencial de GitHub
1. Clona o descarga este repositorio y abre la carpeta raíz.
2. Navega hacia la carpeta `miner/`.
3. Crea un archivo nuevo y nómbralo exactamente `.env`.
4. Dentro de ese archivo, pega tu token con el siguiente formato:
   ```env
   GITHUB_TOKEN=ghp_tu_token_aqui_12345

### Paso 2: Desplegar el sistema
1. Desde la raíz del proyecto ejecuta el siguiente comando en tu terminal: docker-compose up --build

### Paso 2: Visualización

1. Una vez que los contenedores estén en ejecución, accede al panel de control en tu navegador:

URL: http://localhost:8080