from flask import Flask, render_template
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
from sklearn.linear_model import LogisticRegression
import plotly.graph_objs as go
import plotly.io as pio

app = Flask(__name__)

@app.route('/')
def index():
    # Conexión con Google Sheets
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        "C:/Users/Marieta/Documents/PlatformIO/Projects/termotanque/src/tanque-de-condensados-04115fb3a005.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("prueba 2").sheet1

    # Cargar y limpiar datos
    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    df.columns = df.columns.str.strip()
    df['FechaHora'] = pd.to_datetime(df['FechaHora'], dayfirst=True, errors='coerce')
    df[['Temp 1', 'Temp 2', 'Temp3']] = df[['Temp 1', 'Temp 2', 'Temp3']].apply(pd.to_numeric, errors='coerce')
    df.dropna(inplace=True)
    df = df.sort_values(by='FechaHora')

    # Filtrar últimos 10 registros espaciados cada 10 minutos
    df_grafica = df.set_index('FechaHora').resample('10T').last().dropna().reset_index().tail(10)

    # Pronósticos con regresión logística
    pronosticos = []
    alarma_pronostico = False
    for temp_col in ['Temp 1', 'Temp 2', 'Temp3']:
        df[f'Sube_{temp_col}'] = (df[temp_col].shift(-1) > df[temp_col]).astype(int)
        X = df[['Temp 1', 'Temp 2', 'Temp3']]
        y = df[f'Sube_{temp_col}']
        if y.nunique() > 1:
            model = LogisticRegression()
            model.fit(X, y)
            pred_futuro = model.predict([X.iloc[-1].values])[0]
            pronostico_texto = 'Sube' if pred_futuro == 1 else 'No sube'
            if pred_futuro == 1:
                alarma_pronostico = True  # activa alarma si algún pronóstico indica subida
            pronosticos.append({
                'temperatura': temp_col,
                'pronostico': pronostico_texto,
                'fecha': (df['FechaHora'].max() + pd.Timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
            })
        else:
            pronosticos.append({
                'temperatura': temp_col,
                'pronostico': 'No se puede predecir',
                'fecha': '---'
            })

    # Últimos 10 registros con temperatura > 80 en cualquiera de las 3 columnas
    fallas_tabla = df[
        (df['Temp 1'] > 80) | (df['Temp 2'] > 80) | (df['Temp3'] > 80)
    ].sort_values(by='FechaHora', ascending=False).head(10)

    # Alerta basada en pronóstico
    alerta = alarma_pronostico

    # Gráfica
    colores = ['blue', 'green', 'orange']
    nombres = ['Temp 1', 'Temp 2', 'Temp3']
    traces = []
    for i, col in enumerate(['Temp 1', 'Temp 2', 'Temp3']):
        traces.append(go.Scatter(
            x=df_grafica['FechaHora'], y=df_grafica[col],
            mode='lines+markers',
            name=nombres[i],
            marker=dict(size=8, color=colores[i]),
            text=[f"{col}: {t}°C<br>Fecha: {f}" for f, t in zip(df_grafica['FechaHora'], df_grafica[col])],
            hoverinfo='text'
        ))

    layout = go.Layout(
        title='Temperaturas (últimos 10 registros cada 10 min)',
        xaxis=dict(title='Fecha y Hora'),
        yaxis=dict(title='Temperatura (°C)'),
        hovermode='closest'
    )
    fig = go.Figure(data=traces, layout=layout)
    graph_html = pio.to_html(fig, full_html=False)

    return render_template(
        'index.html',
        graph_html=graph_html,
        fallas=fallas_tabla.to_dict(orient='records'),
        alerta=alerta,
        pronosticos=pronosticos
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)