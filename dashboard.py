import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go

# Configuration de la page (Doit être la première commande)
st.set_page_config(page_title="VALORANT // TRACKER", layout="wide", initial_sidebar_state="expanded")

# --- STYLE CSS PERSONNALISÉ (D.A. VALORANT) ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Teko:wght@500;700&family=Roboto:wght@400;700&display=swap');

/* Fond général (Bleu nuit Valorant) */
.stApp {
    background-color: #0f1923;
    color: #ece8e1;
    font-family: 'Roboto', sans-serif;
}

/* Sidebar */[data-testid="stSidebar"] {
    background-color: #111111;
    border-right: 2px solid #ff4655;
}

/* Titres */
h1, h2, h3 {
    font-family: 'Teko', sans-serif;
    text-transform: uppercase;
    color: #ff4655 !important;
    letter-spacing: 2px;
}

/* Customisation des Metric Cards (Statistiques) */
div[data-testid="stMetric"] {
    background-color: #1f2326;
    border-top: 4px solid #ff4655;
    padding: 15px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.5);
}[data-testid="stMetricValue"] {
    color: #ece8e1 !important;
    font-family: 'Teko', sans-serif;
    font-size: 3rem !important;
}
[data-testid="stMetricLabel"] {
    color: #8b978f !important;
    text-transform: uppercase;
    font-weight: bold;
    letter-spacing: 1px;
}

/* Lignes de séparation */
hr {
    border-color: #ff4655 !important;
    opacity: 0.3;
}
</style>
""", unsafe_allow_html=True)

# --- FONCTION DE CHARGEMENT ---
def load_and_merge_data(uploaded_files):
    all_matches =[]
    
    for uploaded_file in uploaded_files:
        data = json.load(uploaded_file)
        for m in data.get("matches", []):
            m['date_dt'] = pd.to_datetime(m['date'])
            all_matches.append(m)
            
    if not all_matches:
        return pd.DataFrame()

    df = pd.DataFrame(all_matches)
    
    # Dédoublonnage : on garde le match le plus récent en cas d'ID identique
    df = df.sort_values(by='date_dt').drop_duplicates(subset='match_id', keep='last')
    return df

# --- CONFIGURATION GRAPHIQUES PLOTLY ---
def apply_val_theme(fig):
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color='#ece8e1',
        margin=dict(t=20, b=30, l=30, r=30), 
        xaxis=dict(showgrid=True, gridcolor='#333333', zeroline=False),
        yaxis=dict(showgrid=True, gridcolor='#333333', zeroline=False)
    )
    return fig

# --- INTERFACE UTILISATEUR ---
st.title("VALORANT // PERFORMANCE HUB")
st.sidebar.markdown("## // TRANSMISSION DE DONNÉES")

uploaded_files = st.sidebar.file_uploader("SÉLECTIONNER LES FICHIERS JSON", type="json", accept_multiple_files=True)

if uploaded_files:
    df = load_and_merge_data(uploaded_files)
    
    if not df.empty:
        # Nettoyage
        df['kills'] = pd.to_numeric(df['kills'])
        df['deaths'] = pd.to_numeric(df['deaths'])
        df['assists'] = pd.to_numeric(df['assists'])
        df['acs'] = pd.to_numeric(df['acs'])
        df['damage_per_round'] = pd.to_numeric(df['damage_per_round'])
        df['headshot_pct'] = pd.to_numeric(df['headshot_pct'])
        df['day'] = df['date_dt'].dt.date
        
        # --- STATISTIQUES GLOBALES ---
        win_rate = (df['result'] == 'victory').mean() * 100
        avg_kd = (df['kills'].sum() / df['deaths'].sum()) if df['deaths'].sum() > 0 else 0
        avg_acs = df['acs'].mean()
        avg_hs = df['headshot_pct'].mean()
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("MATCHS JOUÉS", len(df))
        c2.metric("WIN RATE", f"{win_rate:.1f}%")
        c3.metric("K/D RATIO", f"{avg_kd:.2f}")
        c4.metric("ACS MOYEN", f"{avg_acs:.0f}")
        c5.metric("HEADSHOT %", f"{avg_hs:.1f}%")

        st.markdown("<hr>", unsafe_allow_html=True)

        # --- LIGNE 1 : MAPS & AGENTS ---
        col_charts_1, col_charts_2 = st.columns(2)

        with col_charts_1:
            st.markdown("### // TOP AGENTS (V/D)")
            
            # Préparation des données avec traduction des résultats
            df_agent = df.copy()
            df_agent['result_fr'] = df_agent['result'].map({'victory': 'Victoire', 'defeat': 'Défaite'})
            agent_data = df_agent.groupby(['agent', 'result_fr']).size().reset_index(name='count')
            
            # Ordre des agents du plus joué au moins joué
            agent_order = df['agent'].value_counts().index[::-1]
            
            # Couleurs thématiques (Vert = Victoire, Rouge = Défaite)
            color_map = {'Victoire': '#00ffba', 'Défaite': '#ff4655'}
            
            fig_agent = px.bar(agent_data, x='count', y='agent', color='result_fr', 
                               orientation='h', color_discrete_map=color_map, text='count')
            fig_agent = apply_val_theme(fig_agent)
            
            fig_agent.update_layout(
                yaxis={'categoryorder': 'array', 'categoryarray': agent_order},
                barmode='stack', # Empile les victoires et défaites
                xaxis_title="Nombre de matchs",
                yaxis_title="Agents",
                legend_title_text="" # Retire le titre de la légende pour plus de propreté
            )
            # Personnalisation de la police des chiffres à l'intérieur des barres
            fig_agent.update_traces(textfont=dict(family='Teko', size=18, color='#0f1923'), textposition='inside')
            
            st.plotly_chart(fig_agent, use_container_width=True)

        with col_charts_2:
            st.markdown("### // WIN RATE PAR MAP")
            
            # Calcul des victoires, défaites et win rate par map
            map_stats = df.groupby('map')['result'].value_counts().unstack().fillna(0)
            
            if 'victory' not in map_stats.columns: map_stats['victory'] = 0
            if 'defeat' not in map_stats.columns: map_stats['defeat'] = 0
                
            # Calcul du Win Rate en %
            map_stats['win_rate'] = (map_stats['victory'] / (map_stats['victory'] + map_stats['defeat'])) * 100
            map_stats = map_stats.sort_values('win_rate')
            
            # Création du label "XV - YD" pour le texte dans la barre
            map_stats['label'] = map_stats['victory'].astype(int).astype(str) + "V - " + map_stats['defeat'].astype(int).astype(str) + "D"

            fig_map = px.bar(map_stats, x='win_rate', y=map_stats.index, orientation='h',
                             color='win_rate', color_continuous_scale=['#1f2326', '#ff4655'],
                             text='label') # Ajout du texte
                             
            fig_map = apply_val_theme(fig_map)
            
            # Ajout du nom de l'axe Y et suppression de la légende couleur
            fig_map.update_layout(
                coloraxis_showscale=False, 
                xaxis_title="Win Rate (%)", 
                yaxis_title="Maps"
            )
            # Stylisation du texte (V/D) dans les barres
            fig_map.update_traces(textfont=dict(family='Teko', size=16, color='#ece8e1'), textposition='auto')
            
            st.plotly_chart(fig_map, use_container_width=True)

        st.markdown("<hr>", unsafe_allow_html=True)

        # --- LIGNE 2 : ÉVOLUTION TEMPORELLE (ACS & HEADSHOT) ---
        col_trend_1, col_trend_2 = st.columns(2)

        with col_trend_1:
            st.markdown("### // ÉVOLUTION DE L'ACS")
            df_sorted = df.sort_values('date_dt')
            fig_acs = px.line(df_sorted, x='date_dt', y='acs', markers=True,
                              hover_data=['agent', 'map', 'score'])
            fig_acs.update_traces(line_color='#ece8e1', marker=dict(size=8, color='#ff4655'))
            fig_acs = apply_val_theme(fig_acs)
            fig_acs.update_layout(xaxis_title="Date", yaxis_title="Combat Score (ACS)")
            st.plotly_chart(fig_acs, use_container_width=True)

        with col_trend_2:
            st.markdown("### // ÉVOLUTION DU HEADSHOT % (PAR JOUR)")
            hs_daily = df.groupby('day')['headshot_pct'].mean().reset_index()
            fig_hs = px.line(hs_daily, x='day', y='headshot_pct', markers=True)
            fig_hs.update_traces(line_color='#ff4655', marker=dict(size=8, color='#0f1923', line=dict(width=2, color='#ff4655')), fill='tozeroy', fillcolor='rgba(255, 70, 85, 0.1)')
            fig_hs = apply_val_theme(fig_hs)
            fig_hs.update_layout(xaxis_title="Jour", yaxis_title="Headshot Moyen (%)")
            st.plotly_chart(fig_hs, use_container_width=True)

        st.markdown("<hr>", unsafe_allow_html=True)

        # --- TABLEAU DE DÉTAILS ---
        st.markdown("### // REGISTRE DES COMBATS")
        display_cols =['date', 'map', 'agent', 'result', 'score', 'kills', 'deaths', 'acs', 'headshot_pct']
        
        st.dataframe(df[display_cols].sort_values(by='date', ascending=False), use_container_width=True)

    else:
        st.error("Rapport d'erreur : Les fichiers JSON sont corrompus ou vides.")
else:
    st.info("En attente de connexion... Veuillez charger vos fichiers JSON dans le terminal de gauche.")