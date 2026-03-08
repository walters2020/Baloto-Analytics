# Análisis de Resultados Baloto Colombia

Este repositorio contiene scripts en Python para automatizar la descarga, análisis y predicción de resultados del sorteo Baloto en Colombia.

## Estructura del Proyecto

- `getdata.py`: Script para descargar el histórico de resultados desde el sitio oficial de Baloto. Genera el archivo `baloto_resultados.xlsx`.
- `anomalias.py`: Realiza un análisis estadístico (Chi-cuadrado) para detectar posibles anomalías en la frecuencia de los números.
- `Predict.py`: Realiza un análisis exhaustivo de patrones, números calientes/fríos, y genera predicciones basadas en frecuencias históricas. Genera `baloto_analisis_output.xlsx`.
- `baloto_resultados.xlsx`: Tabla con el histórico de resultados descargados (Baloto y Revancha).
- `baloto_analisis_output.xlsx`: Archivo con múltiples pestañas que contienen estadísticas detalladas y predicciones.

## Requisitos

- Python 3.10+
- Librerías: `pandas`, `requests`, `beautifulsoup4`, `openpyxl`, `numpy`

```bash
pip install pandas requests beautifulsoup4 openpyxl numpy
```

## Dashboard de Looker Studio

Puedes ver el Dashboard interactivo con los resultados y el análisis estadístico en el siguiente enlace:
[Enlace al Dashboard] (Pendiente de publicación)

---
*Automatizado con Antigravity AI*
