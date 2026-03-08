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

## Dashboard de Analítica
El dashboard interactivo está disponible en Looker Studio:
[**Baloto Analytics Dashboard**](https://lookerstudio.google.com/reporting/8e0cffb3-2c09-4113-991d-c7be561e4b33)

### Estructura del Dashboard:
1. **Histórico de Resultados:** Tabla detallada con todos los sorteos descargados.
2. **Estadísticas y Predicciones:** Gráficos de barra de números calientes (Hot Numbers) y análisis de patrones.

---
## Desarrollo y Automatización
- `getdata.py`: Descarga y limpia los resultados.
- `Predict.py`: Genera análisis estadístico avanzado.
- `export_csv.py`: Prepara los datos para Looker Studio.
- Datos sincronizados vía GitHub RAW para actualización automática.

---
*Automatizado con Antigravity AI*
