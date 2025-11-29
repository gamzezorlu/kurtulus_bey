import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO
from calendar import monthrange

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
    df = pd.read_excel(uploaded_file)
    
    st.subheader("📋 Yüklenen Veriler")
    st.dataframe(df.head(10))
    
    # Veri yapısını anla
    # İlk kolon: Tesisat ID
    # Diğer kolonlar: Tarih başlıklı tüketim verileri
    
    facility_col = df.columns[0]
    date_columns = df.columns[1:]
    
    st.info(f"✅ Tespit Edilen: {len(df)} tesisat, {len(date_columns)} dönem")
    
    # Tarihleri parse et
    dates_parsed = []
    days_in_period = []
    
    for date_str in date_columns:
        try:
            date_obj = pd.to_datetime(date_str)
            dates_parsed.append(date_obj)
            # Gün sayısını tarihin gün kısmından al (örn: 24.11.2025 = 24 gün)
            day_num = int(str(date_str).split('.')[0])
            days_in_period.append(day_num)
        except:
            st.error(f"Tarih parse edilemedi: {date_str}")
    
    # Veriyi dönüştür (pivot)
    data_list = []
    
    for facility in df[facility_col]:
        for i, date in enumerate(dates_parsed):
            consumption_value = df[df[facility_col] == facility].iloc[0, i+1]
            
            # #YOK kontrolü
            if isinstance(consumption_value, str) and '#YOK' in str(consumption_value):
                continue
            
            try:
                consumption_value = float(consumption_value)
            except:
                continue
            
            day_count = days_in_period[i]
            
            # 30 günlük normalleştirilmiş tüketim
            normalized = (consumption_value / day_count) * 30
            
            data_list.append({
                'facility_id': facility,
                'date': date,
                'year': date.year,
                'month': date.month,
                'month_name': date.strftime('%B %Y'),
                'days_reported': day_count,
                'raw_consumption': consumption_value,
                'normalized_consumption': normalized
            })
    
    df_work = pd.DataFrame(data_list)
    st.success("✅ Veri işlendi!")
    
    # Anomali Tespiti
    st.header("3️⃣ Anomali Tespiti")
    
    def detect_anomalies(group):
        """Her tesisat için anomali tespiti yap"""
        if len(group) < 2:
            group['expected_consumption'] = group['normalized_consumption'].mean()
            group['std_deviation'] = 0
            group['deviation_percent'] = 0
            group['is_anomaly'] = False
            return group
        
        # Normalized tüketimin ortalaması ve standart sapması
        mean = group['normalized_consumption'].mean()
        std = group['normalized_consumption'].std()
        
        # Sapma yüzdesini hesapla
        group['expected_consumption'] = mean
        group['std_deviation'] = std
        group['deviation_percent'] = ((group['normalized_consumption'] - mean).abs() / mean * 100)
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
        display_cols = ['facility_id', 'month_name', 'raw_consumption', 'days_reported',
                       'normalized_consumption', 'expected_consumption', 'deviation_percent']
        
        anomaly_display = anomalies_df[display_cols].copy()
        anomaly_display['raw_consumption'] = anomaly_display['raw_consumption'].round(2)
        anomaly_display['normalized_consumption'] = anomaly_display['normalized_consumption'].round(2)
        anomaly_display['expected_consumption'] = anomaly_display['expected_consumption'].round(2)
        anomaly_display['deviation_percent'] = anomaly_display['deviation_percent'].round(2)
        
        # Rename for display
        anomaly_display.columns = ['Tesisat ID', 'Dönem', 'Ham Tüketim', 'Gün Sayısı',
                                   'Normalleştirilmiş (30g)', 'Beklenen Ort.', 'Sapma %']
        
        st.dataframe(anomaly_display, use_container_width=True)
        
        # İnceleme Raporu İndir
        st.subheader("📥 İnceleme Raporu İndir")
        
        report_df = anomalies_df[['facility_id', 'date', 'raw_consumption', 'days_reported',
                                  'normalized_consumption', 'expected_consumption',
                                  'deviation_percent', 'month_name']].copy()
        report_df = report_df.sort_values('deviation_percent', ascending=False)
        report_df.columns = ['Tesisat ID', 'Tarih', 'Ham Tüketim', 'Gün Sayısı',
                            'Normalleştirilmiş (30g)', 'Beklenen Ort.', 'Sapma %', 'Dönem']
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            report_df.to_excel(writer, sheet_name='Anomaliler', index=False)
            
            # Tüm veriler
            all_data = df_analysis[['facility_id', 'date', 'raw_consumption', 'days_reported',
                                    'normalized_consumption', 'expected_consumption',
                                    'deviation_percent', 'is_anomaly', 'month_name']].copy()
            all_data.columns = ['Tesisat ID', 'Tarih', 'Ham Tüketim', 'Gün Sayısı',
                               'Normalleştirilmiş (30g)', 'Beklenen Ort.', 'Sapma %', 'Anomali', 'Dönem']
            all_data.to_excel(writer, sheet_name='Tüm Veriler', index=False)
        
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
                name='Normalleştirilmiş Tüketim (30g)',
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
                xaxis_title="Dönem",
                yaxis_title="Normalleştirilmiş Tüketim",
                hovermode='x unified',
                height=400
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
                labels={'deviation_percent': 'Sapma Yüzdesi (%)', 'month_name': 'Dönem'}
            )
            fig2.update_layout(height=400)
            st.plotly_chart(fig2, use_container_width=True)
        
        # Detaylı Tablo
        st.subheader(f"📊 Tesisat {selected_facility} - Detay")
        detail_df = facility_data[['month_name', 'raw_consumption', 'days_reported',
                                   'normalized_consumption', 'expected_consumption',
                                   'deviation_percent', 'is_anomaly']].copy()
        detail_df.columns = ['Dönem', 'Ham Tüketim', 'Gün Sayısı', 'Normalleştirilmiş (30g)',
                            'Beklenen Ort.', 'Sapma %', 'Anomali mi?']
        detail_df['Normalleştirilmiş (30g)'] = detail_df['Normalleştirilmiş (30g)'].round(2)
        detail_df['Beklenen Ort.'] = detail_df['Beklenen Ort.'].round(2)
        detail_df['Sapma %'] = detail_df['Sapma %'].round(2)
        
        st.dataframe(detail_df, use_container_width=True)

else:
    st.info("👆 Başlamak için lütfen Excel dosyanızı yükleyin")
