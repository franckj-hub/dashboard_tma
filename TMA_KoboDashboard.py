#!/usr/bin/env python
# coding: utf-8

import os
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, dcc, html, Input, Output, State
import dash_bootstrap_components as dbc
from datetime import datetime, timedelta
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# =====================================================
# CONFIGURATION KOBO
# =====================================================

TOKEN = "c74687b69db732f0ceab7271687d0f92f1a9c84c"
UID = "aacEWzbiaWLh2UKRYQDgZB"

headers = {"Authorization": f"Token {TOKEN}"}

# =====================================================
# FONCTION POUR RÉCUPÉRER TOUTES LES DONNÉES
# =====================================================

def get_all_kobo_data(uid, headers):
    all_results = []
    url = f"https://kf.kobotoolbox.org/api/v2/assets/{uid}/data/"
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            break
        data = response.json()
        all_results.extend(data["results"])
        url = data.get("next", None)
    return all_results

print("🔄 Chargement des données Kobo...")
results = get_all_kobo_data(UID, headers)
df = pd.DataFrame(results)
print(f"✅ {len(df)} enregistrements chargés")

# =====================================================
# NETTOYAGE RENFORCÉ DES DONNÉES - Version Universelle
# =====================================================

# Supprimer les colonnes complètement vides
df = df.dropna(axis=1, how='all')

# =====================================================
# NETTOYAGE AUTOMATIQUE DE TOUTES LES COLONNES
# =====================================================

# 1. Nettoyer TOUTES les colonnes catégorielles (textes)
for col in df.columns:
    if df[col].dtype == 'object':
        # Remplacer les valeurs vides par 'Non renseigné'
        df[col] = df[col].fillna('Non renseigné')
        # Convertir en string (texte) pour éviter l'erreur float vs str
        df[col] = df[col].astype(str)
        # Nettoyer les valeurs 'nan' ou 'None' qui pourraient rester
        df[col] = df[col].replace(['nan', 'None', 'NaN'], 'Non renseigné')

print("✅ Nettoyage des colonnes textuelles terminé")

# 2. Nettoyer la colonne ÂGE (spécifique car numérique)
if '_4_Quel_est_votre_ge_' in df.columns:
    df['_4_Quel_est_votre_ge_'] = pd.to_numeric(df['_4_Quel_est_votre_ge_'], errors='coerce')
    median_age = df['_4_Quel_est_votre_ge_'].median()
    df['_4_Quel_est_votre_ge_'] = df['_4_Quel_est_votre_ge_'].fillna(median_age)
    print(f"📊 Âges nettoyés - Médiane: {median_age}")

# 3. Nettoyage des dates
if '_submission_time' in df.columns:
    df['_submission_time'] = pd.to_datetime(df['_submission_time'], errors='coerce')
    # Supprimer les dates nulles
    df = df.dropna(subset=['_submission_time'])
    print(f"📅 Dates nettoyées")

OBJECTIF = 400
POURCENTAGE = min(100, (len(df) / OBJECTIF) * 100) if len(df) > 0 else 0

print(f"📊 Après nettoyage: {len(df)} enregistrements valides")
# =====================================================
# LISTE DES VARIABLES DISPONIBLES
# =====================================================

toutes_les_variables = []

# Variables spécifiques importantes
colonnes_importantes = [
    '_1_a_Vous_etes_de_quelle_provi',
    '_3_Quel_est_votre_sexe_',
    '_4_Quel_est_votre_ge_',
    '_6_Quelle_culture_av_durant_le_projet_TMA',
    '_8_Appliquez_vous_l_ue_dans_votre_champ_',
    '_11_A_quel_niveau_tiez_vous_satisfait_',
    '_submitted_by'
]

for col in colonnes_importantes:
    if col in df.columns:
        label = col.replace('_', ' ').replace('1 a', 'Province').replace('3', 'Sexe').replace('4', 'Âge').replace('6', 'Culture').replace('8', 'Engrais').replace('11', 'Satisfaction')
        toutes_les_variables.append({'label': label[:30], 'value': col})

# Ajouter les autres colonnes
for col in df.columns:
    if col not in colonnes_importantes and col not in ['_submission_time', '_id', '_uuid', '_attachments', '_tags', '_notes', '_geolocation', '_xform_id_string', 'meta/instanceID', 'meta/rootUuid']:
        toutes_les_variables.append({'label': col[:30], 'value': col})

# =====================================================
# DASHBOARD
# =====================================================

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

app.layout = dbc.Container([
    # HEADER avec jauge
    dbc.Row([
        dbc.Col([
            html.H1("📊 DASHBOARD TMA - ENDLINE", 
                   className="text-center text-primary mb-2"),
            html.H4(f"📝 {len(df)} / {OBJECTIF} SOUMISSIONS", 
                   className="text-center"),
            html.Div([
                html.Div(f"{POURCENTAGE:.0f}%",
                        style={'textAlign': 'center', 'fontSize': 24, 'fontWeight': 'bold', 'color': '#2c3e50'}),
                html.Div(className="progress", children=[
                    html.Div(className="progress-bar bg-success", 
                            style={'width': f'{POURCENTAGE}%', 'height': '30px'})
                ])
            ]),
            html.P(f"🕐 Mise à jour: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                   className="text-center text-muted mb-4")
        ], width=12)
    ]),
    
    # LIGNE 1: Évolution + Barres horizontales provinces
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("📈 ÉVOLUTION DES SOUMISSIONS"),
                dbc.CardBody([dcc.Graph(id='graph_evolution', style={'height': '400px'})])
            ])
        ], width=6),
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("📊 EFFECTIFS PAR PROVINCE"),
                dbc.CardBody([dcc.Graph(id='graph_provinces', style={'height': '350px'})])
            ])
        ], width=6)
    ], className="mb-4"),
    
    # LIGNE 2: TABLEAU CROISÉ + GRAPHIQUE CÔTE À CÔTE
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🎛️ TABLEAU CROISÉ DYNAMIQUE"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("📊 Variable Ligne:"),
                            dcc.Dropdown(id='pivot_lignes', options=toutes_les_variables, 
                                       value='_1_a_Vous_etes_de_quelle_provi' if '_1_a_Vous_etes_de_quelle_provi' in df.columns else (toutes_les_variables[0]['value'] if toutes_les_variables else None))
                        ], width=6),
                        dbc.Col([
                            html.Label("📈 Variable Colonne:"),
                            dcc.Dropdown(id='pivot_colonnes', options=[{'label': 'Aucune', 'value': None}] + toutes_les_variables, 
                                       value='_3_Quel_est_votre_sexe_' if '_3_Quel_est_votre_sexe_' in df.columns else None)
                        ], width=6)
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Col([
                            html.Label("📊 Type:"),
                            dcc.RadioItems(id='pivot_type', options=[{'label': 'Effectifs', 'value': 'count'}, {'label': 'Pourcentages (%)', 'value': 'percent'}], value='count', inline=True)
                        ], width=12)
                    ]),
                    html.Hr(),
                    html.Div(id='pivot_table', className="table-responsive", style={'maxHeight': '400px', 'overflowY': 'auto'})
                ])
            ])
        ], width=6),
        
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🥧 ANALYSE GRAPHIQUE"),
                dbc.CardBody([
                    dbc.Row([
                        dbc.Col([
                            html.Label("Variable à analyser:"),
                            dcc.Dropdown(id='analyse_variable', options=toutes_les_variables, 
                                       value='_3_Quel_est_votre_sexe_' if '_3_Quel_est_votre_sexe_' in df.columns else (toutes_les_variables[0]['value'] if toutes_les_variables else None))
                        ], width=6),
                        dbc.Col([
                            html.Label("Type de graphique:"),
                            dcc.Dropdown(id='analyse_type', options=[
                                {'label': '🥧 Camembert', 'value': 'pie'},
                                {'label': '📊 Barres empilées', 'value': 'stack'},
                                {'label': '📊 Barres groupées', 'value': 'group'}
                            ], value='pie')
                        ], width=6)
                    ], className="mb-3"),
                    dbc.Row([
                        dbc.Col([
                            html.Label("🎨 Mode:"),
                            dcc.RadioItems(id='analyse_mode', options=[
                                {'label': 'Effectifs', 'value': 'count'},
                                {'label': 'Pourcentages (%)', 'value': 'percent'}
                            ], value='count', inline=True)
                        ], width=12)
                    ]),
                    dcc.Graph(id='graph_analyse', style={'height': '380px'})
                ])
            ])
        ], width=6)
    ], className="mb-4"),
    
    # LIGNE 3: FILTRES GLOBAUX
    dbc.Row([
        dbc.Col([
            dbc.Card([
                dbc.CardHeader("🔍 FILTRES GLOBAUX"),
                dbc.CardBody([
                    html.P("💡 Sélectionnez des valeurs pour filtrer tous les graphiques", 
                           className="text-info small"),
                    
                    dbc.Row([
                        dbc.Col([
                            html.Label("📅 Période"),
                            dcc.RadioItems(id='filtre_periode',
                                options=[
                                    {'label': '7 jours', 'value': 7},
                                    {'label': '30 jours', 'value': 30},
                                    {'label': '90 jours', 'value': 90},
                                    {'label': 'Tout', 'value': 9999}
                                ], value=30, inline=True)
                        ], width=12, className="mb-3")
                    ]),
                    
                    dbc.Row([
                        dbc.Col([
                            html.Label("📍 Province"),
                            dcc.Dropdown(id='filtre_province',
                                options=[{'label': p, 'value': p} for p in sorted(df['_1_a_Vous_etes_de_quelle_provi'].unique())] if '_1_a_Vous_etes_de_quelle_provi' in df.columns else [],
                                multi=True, placeholder="Toutes")
                        ], width=4),
                        
                        dbc.Col([
                            html.Label("👫 Sexe"),
                            dcc.Dropdown(id='filtre_sexe',
                                options=[{'label': s, 'value': s} for s in sorted(df['_3_Quel_est_votre_sexe_'].unique())] if '_3_Quel_est_votre_sexe_' in df.columns else [],
                                multi=True, placeholder="Tous")
                        ], width=4),
                        
                        dbc.Col([
                            html.Label("🌾 Culture"),
                            dcc.Dropdown(id='filtre_culture',
                                options=[{'label': c, 'value': c} for c in sorted(df['_6_Quelle_culture_av_durant_le_projet_TMA'].unique())] if '_6_Quelle_culture_av_durant_le_projet_TMA' in df.columns else [],
                                multi=True, placeholder="Toutes")
                        ], width=4)
                    ], className="mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            html.Label("🌱 Utilisation engrais"),
                            dcc.Dropdown(id='filtre_engrais',
                                options=[{'label': e, 'value': e} for e in sorted(df['_8_Appliquez_vous_l_ue_dans_votre_champ_'].unique())] if '_8_Appliquez_vous_l_ue_dans_votre_champ_' in df.columns else [],
                                multi=True, placeholder="Tous")
                        ], width=4),
                        
                        dbc.Col([
                            html.Label("😊 Satisfaction"),
                            dcc.Dropdown(id='filtre_satisfaction',
                                options=[{'label': s, 'value': s} for s in sorted(df['_11_A_quel_niveau_tiez_vous_satisfait_'].unique())] if '_11_A_quel_niveau_tiez_vous_satisfait_' in df.columns else [],
                                multi=True, placeholder="Tous")
                        ], width=4),
                        
                        dbc.Col([
                            html.Label("👤 Enquêteur"),
                            dcc.Dropdown(id='filtre_enqueteur',
                                options=[{'label': e, 'value': e} for e in sorted(df['_submitted_by'].unique())] if '_submitted_by' in df.columns else [],
                                multi=True, placeholder="Tous")
                        ], width=4)
                    ], className="mb-3"),
                    
                    dbc.Row([
                        dbc.Col([
                            html.Label("📊 Âge"),
                            dcc.RangeSlider(
                                id='filtre_age',
                                min=int(df['_4_Quel_est_votre_ge_'].min()) if '_4_Quel_est_votre_ge_' in df.columns and not df['_4_Quel_est_votre_ge_'].isna().all() else 18,
                                max=int(df['_4_Quel_est_votre_ge_'].max()) if '_4_Quel_est_votre_ge_' in df.columns and not df['_4_Quel_est_votre_ge_'].isna().all() else 100,
                                step=1,
                                value=[int(df['_4_Quel_est_votre_ge_'].min()) if '_4_Quel_est_votre_ge_' in df.columns and not df['_4_Quel_est_votre_ge_'].isna().all() else 18,
                                       int(df['_4_Quel_est_votre_ge_'].max()) if '_4_Quel_est_votre_ge_' in df.columns and not df['_4_Quel_est_votre_ge_'].isna().all() else 100],
                                marks={18: '18', 30: '30', 50: '50', 70: '70', 100: '100'}
                            )
                        ], width=12)
                    ])
                ])
            ])
        ], width=12)
    ], className="mb-4")
    
], fluid=True)

# =====================================================
# FONCTION DE FILTRAGE (Version robuste)
# =====================================================

def filter_data(dff, periode, provinces, sexe, culture, engrais, satisfaction, enqueteurs, age_range):
    dff = dff.copy()
    
    if dff.empty:
        return dff
    
    # Filtre période
    if periode != 9999 and '_submission_time' in dff.columns:
        start_date = datetime.now().date() - timedelta(days=periode)
        dff['date_only'] = pd.to_datetime(dff['_submission_time']).dt.date
        dff = dff[dff['date_only'] >= start_date]
    
    # Filtre province
    if provinces and '_1_a_Vous_etes_de_quelle_provi' in dff.columns:
        dff = dff[dff['_1_a_Vous_etes_de_quelle_provi'].isin(provinces)]
    
    # Filtre sexe
    if sexe and '_3_Quel_est_votre_sexe_' in dff.columns:
        dff = dff[dff['_3_Quel_est_votre_sexe_'].isin(sexe)]
    
    # Filtre culture
    if culture and '_6_Quelle_culture_av_durant_le_projet_TMA' in dff.columns:
        dff = dff[dff['_6_Quelle_culture_av_durant_le_projet_TMA'].isin(culture)]
    
    # Filtre engrais
    if engrais and '_8_Appliquez_vous_l_ue_dans_votre_champ_' in dff.columns:
        dff = dff[dff['_8_Appliquez_vous_l_ue_dans_votre_champ_'].isin(engrais)]
    
    # Filtre satisfaction
    if satisfaction and '_11_A_quel_niveau_tiez_vous_satisfait_' in dff.columns:
        dff = dff[dff['_11_A_quel_niveau_tiez_vous_satisfait_'].isin(satisfaction)]
    
    # Filtre enquêteur
    if enqueteurs and '_submitted_by' in dff.columns:
        dff = dff[dff['_submitted_by'].isin(enqueteurs)]
    
    # Filtre âge (Version ROBUSTE)
    if '_4_Quel_est_votre_ge_' in dff.columns:
        # Convertir en numérique, forcer les erreurs en NaN
        dff['_4_Quel_est_votre_ge_'] = pd.to_numeric(dff['_4_Quel_est_votre_ge_'], errors='coerce')
        # Supprimer les lignes où l'âge est NaN
        dff = dff.dropna(subset=['_4_Quel_est_votre_ge_'])
        # Appliquer le filtre de plage
        dff = dff[(dff['_4_Quel_est_votre_ge_'] >= age_range[0]) & (dff['_4_Quel_est_votre_ge_'] <= age_range[1])]
    
    return dff

# =====================================================
# CALLBACKS (IDENTIQUES À L'ORIGINAL)
# =====================================================

# Graphique évolution
@app.callback(
    Output('graph_evolution', 'figure'),
    Input('filtre_periode', 'value'),
    Input('filtre_province', 'value'),
    Input('filtre_sexe', 'value'),
    Input('filtre_culture', 'value'),
    Input('filtre_engrais', 'value'),
    Input('filtre_satisfaction', 'value'),
    Input('filtre_enqueteur', 'value'),
    Input('filtre_age', 'value')
)
def update_evolution(periode, provinces, sexe, culture, engrais, satisfaction, enqueteurs, age_range):
    dff = filter_data(df, periode, provinces, sexe, culture, engrais, satisfaction, enqueteurs, age_range)
    
    if dff.empty or '_submission_time' not in dff.columns:
        return go.Figure().update_layout(title="Aucune donnée pour ces filtres")
    
    daily = dff.groupby(dff['_submission_time'].dt.date).size().reset_index()
    daily.columns = ['date', 'soumissions']
    daily = daily.sort_values('date')
    daily['cumul'] = daily['soumissions'].cumsum()
    
    fig = go.Figure()
    fig.add_trace(go.Bar(x=daily['date'], y=daily['soumissions'], name='Journalier', marker_color='steelblue'))
    fig.add_trace(go.Scatter(x=daily['date'], y=daily['cumul'], name='Cumul', mode='lines+markers', marker_color='orange', yaxis='y2'))
    fig.update_layout(title=f"📈 {len(dff)} soumissions", xaxis_title="Date", yaxis_title="Par jour", yaxis2=dict(title="Cumul", overlaying='y', side='right'), template='plotly_white', height=400)
    return fig

# Graphique provinces
@app.callback(
    Output('graph_provinces', 'figure'),
    Input('filtre_periode', 'value'),
    Input('filtre_province', 'value'),
    Input('filtre_sexe', 'value'),
    Input('filtre_culture', 'value'),
    Input('filtre_engrais', 'value'),
    Input('filtre_satisfaction', 'value'),
    Input('filtre_enqueteur', 'value'),
    Input('filtre_age', 'value')
)
def update_provinces(periode, provinces, sexe, culture, engrais, satisfaction, enqueteurs, age_range):
    dff = filter_data(df, periode, provinces, sexe, culture, engrais, satisfaction, enqueteurs, age_range)
    province_col = '_1_a_Vous_etes_de_quelle_provi'
    
    if dff.empty or province_col not in dff.columns:
        return go.Figure().update_layout(title="Aucune donnée")
    
    counts = dff[province_col].value_counts().reset_index()
    counts.columns = ['Province', 'Effectifs']
    counts = counts.sort_values('Effectifs')
    
    fig = px.bar(counts, x='Effectifs', y='Province', orientation='h', 
                title=f"📊 Effectifs par province - {len(dff)} soumissions",
                color='Effectifs', color_continuous_scale='Viridis', text='Effectifs')
    fig.update_layout(template='plotly_white', height=350)
    fig.update_traces(textposition='outside')
    return fig

# Tableau croisé
@app.callback(
    Output('pivot_table', 'children'),
    Input('pivot_lignes', 'value'),
    Input('pivot_colonnes', 'value'),
    Input('pivot_type', 'value'),
    Input('filtre_periode', 'value'),
    Input('filtre_province', 'value'),
    Input('filtre_sexe', 'value'),
    Input('filtre_culture', 'value'),
    Input('filtre_engrais', 'value'),
    Input('filtre_satisfaction', 'value'),
    Input('filtre_enqueteur', 'value'),
    Input('filtre_age', 'value')
)
def update_pivot(lignes, colonnes, type_aff, periode, provinces, sexe, culture, engrais, satisfaction, enqueteurs, age_range):
    dff = filter_data(df, periode, provinces, sexe, culture, engrais, satisfaction, enqueteurs, age_range)
    
    if dff.empty or not lignes or lignes not in dff.columns:
        return html.Div("Aucune donnée", className="alert alert-warning")
    
    if colonnes and colonnes in dff.columns:
        pivot = pd.crosstab(dff[lignes], dff[colonnes], margins=True, margins_name='TOTAL')
        if type_aff == 'percent':
            pivot_num = pivot.drop('TOTAL').drop('TOTAL', axis=1)
            pivot_pct = (pivot_num.div(pivot_num.sum().sum()) * 100).round(1)
            pivot_pct.loc['TOTAL'] = pivot.loc['TOTAL']
            pivot_pct['TOTAL'] = pivot['TOTAL']
            display_df = pivot_pct.fillna(0)
            title = "Tableau croisé - Pourcentages (%)"
        else:
            display_df = pivot
            title = "Tableau croisé - Effectifs"
    else:
        counts = dff[lignes].value_counts().reset_index()
        counts.columns = [lignes, 'Effectifs']
        counts['%'] = (counts['Effectifs'] / counts['Effectifs'].sum() * 100).round(1)
        display_df = counts
        title = f"Répartition de {lignes}"
    
    return html.Div([
        html.H6(title, className="text-primary"),
        html.Table([
            html.Thead(html.Tr([html.Th('')] + [html.Th(col) for col in display_df.columns if col != 'index'])),
            html.Tbody([
                html.Tr([html.Th(str(idx), style={'fontWeight': 'bold'})] + 
                       [html.Td(display_df.iloc[i, j]) for j, col in enumerate(display_df.columns) if col != 'index'])
                for i, idx in enumerate(display_df.index)
            ])
        ], className="table table-striped table-bordered table-hover table-sm")
    ])

# Graphique analyse
@app.callback(
    Output('graph_analyse', 'figure'),
    Input('analyse_variable', 'value'),
    Input('analyse_type', 'value'),
    Input('analyse_mode', 'value'),
    Input('filtre_periode', 'value'),
    Input('filtre_province', 'value'),
    Input('filtre_sexe', 'value'),
    Input('filtre_culture', 'value'),
    Input('filtre_engrais', 'value'),
    Input('filtre_satisfaction', 'value'),
    Input('filtre_enqueteur', 'value'),
    Input('filtre_age', 'value')
)
def update_analyse(variable, graph_type, mode, periode, provinces, sexe, culture, engrais, satisfaction, enqueteurs, age_range):
    dff = filter_data(df, periode, provinces, sexe, culture, engrais, satisfaction, enqueteurs, age_range)
    
    if dff.empty or not variable or variable not in dff.columns:
        return go.Figure().update_layout(title="Sélectionnez une variable")
    
    counts = dff[variable].value_counts().reset_index()
    counts.columns = ['categorie', 'effectif']
    
    if mode == 'percent':
        counts['effectif'] = (counts['effectif'] / counts['effectif'].sum() * 100).round(1)
        titre_suffixe = "(%)"
    else:
        titre_suffixe = f"(n={len(dff)})"
    
    if graph_type == 'pie':
        fig = px.pie(counts, names='categorie', values='effectif', 
                    title=f"🥧 {variable} {titre_suffixe}",
                    color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_traces(textposition='inside', textinfo='percent+label')
    else:
        fig = px.bar(counts, x='categorie', y='effectif', 
                    title=f"📊 {variable} {titre_suffixe}",
                    color='categorie', text='effectif',
                    barmode='group' if graph_type == 'group' else 'relative')
        fig.update_traces(textposition='outside')
        fig.update_layout(showlegend=False)
    
    fig.update_layout(template='plotly_white', height=380)
    return fig

# =====================================================
# LANCEMENT
# =====================================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8056))
    print("\n" + "="*60)
    print("🚀 DASHBOARD TMA - VERSION CORRIGÉE")
    print("="*60)
    print(f"\n📊 {len(df)} / {OBJECTIF} SOUMISSIONS")
    print(f"📈 Objectif restant: {max(0, OBJECTIF - len(df))} soumissions")
    print("\n🔍 Filtres disponibles sur TOUTES les variables")
    print("\n📍 Lien public bientôt disponible")
    print("="*60 + "\n")
    
    app.run(debug=False, host='0.0.0.0', port=port)
