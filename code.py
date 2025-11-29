import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO

st.set_page_config(page_title="Anomali Tespiti Sistemi", layout="wide")

st.title("📊 Uzaktan Okumalı Sayaç - Anomali Tespiti Sistemi")

# Sidebar - Ayarlar
st.sidebar.header("⚙️ Ayarlar")
anomali_threshold = st.sidebar.slider(
    "Anomali Eşik Değeri (%)", 
    5, 50, 20,
    help="Standart sapmanın kaçıncı yüzdesini anomali olarak işaretleyelim?"
)

# Veri Yükleme
st.header("1️⃣ Veri Yükleme")
uploaded_file = st.file_uploader("Excel dosyanızı yükleyin", type=["xlsx", "xls"])

if uploaded_file:
    # Excel'i oku
    xls = pd.ExcelFile(uploaded_file)
    sheet_names = xls.sheet_names
    
    selected_sheet = st.selectbox("Sayfayı seçin:", sheet_names)
    df = pd.read_excel(uploaded_file, sheet_name=selected_sheet)
    
    st.subheader("📋 Yüklenen Veriler")
    st.dataframe(df.head(10))
    
    # Kolon seçimi
    st.header("2️⃣ Kolon Eşleştirmesi")
    cols = df.columns.tolist()
    
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        facility_col = st.selectbox("Tesisat ID:", cols, index=0)
    with col2:
        date_col = st.selectbox("Tarih:", cols, index=1)
    with col3:
        consumption_col = st.selectbox("Tüketim:", cols, index=2)
    with col4:
        days_col = st.selectbox("Gün Sayısı:", cols, index=3)
    with col5:
        month_col = st.selectbox("Ay/Dönem:", cols, index=4)
    
    # Veriyi işle
    df_work = df[[facility_col, date_col, consumption_col, days_col, month_col]].copy()
    df_work.columns = ['facility_id', 'date', 'consumption', 'days', 'month']
    
    # Tarih dönüşümü
    df_work['date'] = pd.to_datetime(df_work['date'])
    df_work['year'] = df_work['date'].dt.year
    df_work['month_num'] = df_work['date'].dt.month
    df_work['month_name'] = df_work['date'].dt.strftime('%B %Y')
    
    # Normalizasyon: 30 güne dönüştür
    df_work['normalized_consumption'] = (df_work['consumption'] / df_work['days']) * 30
    
    st.success("✅ Veri işlendi!")
    
    # Anomali Tespiti
    st.header("3️⃣ Anomali Tespiti")
    
    def detect_anomalies(group):
        """Her tesisat için anomali tespiti yap"""
        if len(group) < 2:
            return group
        
        # Normalized tüketimin ortalaması ve standart sapması
        mean = group['normalized_consumption'].mean()
        std = group['normalized_consumption'].std()
        
        # Eşik değeri hesapla
        threshold = mean * (anomali_threshold / 100)
        
        # Anomali işareti
        group['expected_consumption'] = mean
        group['std_deviation'] = std
        group['deviation_percent'] = ((group['normalized_consumption'] - mean) / mean * 100).abs()
        group['is_anomaly'] = (group['deviation_percent'] > anomali_threshold)
        
        return group
    
    # Her tesisat için anomali tespiti yap
    df_analysis = df_work.groupby('facility_id', group_keys=False).apply(detect_anomalies)
    
    # Anomali Özeti
    col1, col2, col3 = st.columns(3)
    with col1:
        total_facilities = df_analysis['facility_id'].nunique()
        st.metric("Toplam Tesisat", total_facilities)
    with col2:
        anomalous = df_analysis[df_analysis['is_anomaly']].shape[0]
        st.metric("Anomali Sayısı", anomalous)
    with col3:
        anomaly_ratio = (anomalous / len(df_analysis) * 100) if len(df_analysis) > 0 else 0
        st.metric("Anomali Oranı", f"{anomaly_ratio:.1f}%")
    
    # Anomalileri göster
    st.subheader("🚨 Tespit Edilen Anomaliler")
    
    anomalies_df = df_analysis[df_analysis['is_anomaly']].copy()
    anomalies_df = anomalies_df.sort_values('deviation_percent', ascending=False)
    
    if len(anomalies_df) > 0:
        display_cols = ['facility_id', 'month_name', 'consumption', 'days', 
                       'normalized_consumption', 'expected_consumption', 
                       'deviation_percent']
        
        anomaly_display = anomalies_df[display_cols].copy()
        anomaly_display['normalized_consumption'] = anomaly_display['normalized_consumption'].round(2)
        anomaly_display['expected_consumption'] = anomaly_display['expected_consumption'].round(2)
        anomaly_display['deviation_percent'] = anomaly_display['deviation_percent'].round(2)
        
        st.dataframe(anomaly_display, use_container_width=True)
        
        # İnceleme Raporu İndir
        st.subheader("📥 İnceleme Raporu Indir")
        
        report_df = anomalies_df[['facility_id', 'date', 'consumption', 'days', 
                                   'normalized_consumption', 'expected_consumption',
                                   'deviation_percent']].copy()
        report_df = report_df.sort_values('deviation_percent', ascending=False)
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            report_df.to_excel(writer, sheet_name='Anomaliler', index=False)
            df_analysis.to_excel(writer, sheet_name='Tüm Veriler', index=False)
        
        output.seek(0)
        st.download_button(
            label="📊 Raporu Excel Olarak İndir",
            data=output.getvalue(),
            file_name=f"anomali_raporu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.info("ℹ️ Anomali tespit edilmedi!")
    
    # Görselleştirme
    st.header("4️⃣ Görselleştirme")
    
    # Tesisat seçimi
    facilities = sorted(df_analysis['facility_id'].unique())
    selected_facility = st.selectbox("Tesisat Seçin:", facilities)
    
    facility_data = df_analysis[df_analysis['facility_id'] == selected_facility].sort_values('date')
    
    if len(facility_data) > 0:
        col1, col2 = st.columns(2)
        
        with col1:
            # Trend Grafiği
            fig1 = go.Figure()
            
            fig1.add_trace(go.Scatter(
                x=facility_data['month_name'],
                y=facility_data['normalized_consumption'],
                mode='lines+markers',
                name='Normalleştirilmiş Tüketim',
                line=dict(color='blue', width=2),
                marker=dict(size=8)
            ))
            
            fig1.add_hline(
                y=facility_data['expected_consumption'].iloc[0],
                line_dash="dash",
                line_color="green",
                annotation_text="Beklenen Ortalama"
            )
            
            # Anomaliyi işaretle
            anomaly_points = facility_data[facility_data['is_anomaly']]
            if len(anomaly_points) > 0:
                fig1.add_trace(go.Scatter(
                    x=anomaly_points['month_name'],
                    y=anomaly_points['normalized_consumption'],
                    mode='markers',
                    name='Anomali',
                    marker=dict(color='red', size=12, symbol='x')
                ))
            
            fig1.update_layout(
                title=f"Tesisat {selected_facility} - Tüketim Trendi",
                xaxis_title="Ay",
                yaxis_title="Normalleştirilmiş Tüketim (30 gün)",
                hovermode='x unified'
            )
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            # Sapma Yüzdeleri
            fig2 = px.bar(
                facility_data.sort_values('deviation_percent', ascending=True),
                x='deviation_percent',
                y='month_name',
                orientation='h',
                color='is_anomaly',
                color_discrete_map={True: 'red', False: 'lightblue'},
                title=f"Tesisat {selected_facility} - Sapmalar",
                labels={'deviation_percent': 'Sapma Yüzdesi (%)', 'month_name': 'Ay'}
            )
            st.plotly_chart(fig2, use_container_width=True)
        
        # Detaylı Tablo
        st.subheader(f"📊 Tesisat {selected_facility} - Detay")
        detail_df = facility_data[['date', 'consumption', 'days', 
                                   'normalized_consumption', 'expected_consumption',
                                   'deviation_percent', 'is_anomaly']].copy()
        st.dataframe(detail_df, use_container_width=True)

else:
    st.info("👆 Başlamak için lütfen bir Excel dosyası yükleyin")
