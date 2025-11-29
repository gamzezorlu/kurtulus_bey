import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import plotly.graph_objects as go
import plotly.express as px
from io import BytesIO
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Anomali Tespiti Sistemi", layout="wide")

st.title("🔍 Anomali Tespiti Sistemi - Detaylı Analiz")
st.markdown("---")

# Sidebar - Ayarlar
with st.sidebar:
    st.header("⚙️ Yapılandırma")
    
    st.subheader("📊 Anomali Algılama Yöntemi")
    detection_method = st.radio(
        "Hangi yöntemi kullanmak istiyorsun?",
        ["Standart Sapma (Z-Score)", "IQR (Çeyrekler Arası)", "Karşılaştırmalı Analiz"]
    )
    
    if detection_method == "Standart Sapma (Z-Score)":
        threshold = st.slider("Z-Score Eşik Değeri", 1.0, 3.0, 2.0, 0.1)
        st.caption("2.0 = Normal sapmaları, 3.0 = Extreme sapmaları yakalar")
    
    elif detection_method == "IQR (Çeyrekler Arası)":
        multiplier = st.slider("IQR Çarpanı", 1.0, 3.0, 1.5, 0.1)
        st.caption("1.5 = Standart, 3.0 = Çok katı")
    
    else:
        comp_threshold = st.slider("Karşılaştırma Eşik (%)", 10, 50, 25)
        st.caption("Referans değerden % sapma")

# Veri Yükleme
st.header("📁 Adım 1: Veri Yükleme")

uploaded_file = st.file_uploader("Excel dosyasını yükle", type=["xlsx", "xls"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Tespit Edilen Tesisat Sayısı", len(df))
    with col2:
        st.metric("Tespit Edilen Dönem Sayısı", len(df.columns) - 1)
    
    st.subheader("📋 Yüklenen Veri Örneği")
    st.dataframe(df.head(10), use_container_width=True)
    
    # ============ VERİ DÖNÜŞTÜRME ============
    st.header("🔄 Adım 2: Veri Hazırlama ve Normalleştirilme")
    
    facility_col = df.columns[0]
    date_columns = df.columns[1:]
    
    # Tarihleri parse et
    dates_parsed = []
    days_in_period = []
    
    for date_str in date_columns:
        try:
            date_obj = pd.to_datetime(date_str)
            dates_parsed.append(date_obj)
            day_num = int(str(date_str).split('.')[0])
            days_in_period.append(day_num)
        except:
            pass
    
    # Veriyi dönüştür
    data_list = []
    
    for facility in df[facility_col]:
        for i, date in enumerate(dates_parsed):
            consumption_value = df[df[facility_col] == facility].iloc[0, i+1]
            
            if isinstance(consumption_value, str) and '#YOK' in str(consumption_value):
                continue
            
            try:
                consumption_value = float(consumption_value)
            except:
                continue
            
            day_count = days_in_period[i]
            normalized = (consumption_value / day_count) * 30
            
            data_list.append({
                'facility_id': facility,
                'date': date,
                'year': date.year,
                'month': date.month,
                'month_name': date.strftime('%b %Y'),
                'days_reported': day_count,
                'raw_consumption': consumption_value,
                'normalized_consumption': normalized
            })
    
    df_work = pd.DataFrame(data_list)
    
    # Normalleştirilme açıklaması
    with st.expander("📚 Normalleştirilme Nasıl Çalışıyor?"):
        st.markdown("""
        ### Normalleştirilme Formülü:
        ```
        Normalleştirilmiş Tüketim = (Ham Tüketim / Raporlanan Gün Sayısı) × 30
        ```
        
        **Örnek:**
        - Kasım ayında 24 gün için 22.874 m³ tüketim
        - Günlük ortalama = 22.874 / 24 = 0.953 m³/gün
        - 30 günde tahmini = 0.953 × 30 = **28.59 m³**
        
        **Neden yapıyoruz?**
        - Aylar farklı gün sayılarına sahip (28-31 gün)
        - Kısmi veri (24 gün gibi) tam aya çıkarmak için
        - Tüm dönemleri karşılaştırılabilir hale getirmek
        """)
    
    st.success("✅ Veriler normalleştirildi!")
    
    # ============ ANOMALİ TESPİTİ ============
    st.header("🎯 Adım 3: Anomali Tespit Yöntemleri")
    
    def apply_zscore_detection(group, threshold):
        """Z-Score tabanlı anomali tespiti"""
        mean = group['normalized_consumption'].mean()
        std = group['normalized_consumption'].std()
        
        if std == 0:
            group['z_score'] = 0
            group['method_anomaly'] = False
        else:
            group['z_score'] = np.abs((group['normalized_consumption'] - mean) / std)
            group['method_anomaly'] = group['z_score'] > threshold
        
        return group
    
    def apply_iqr_detection(group, multiplier):
        """IQR tabanlı anomali tespiti"""
        Q1 = group['normalized_consumption'].quantile(0.25)
        Q3 = group['normalized_consumption'].quantile(0.75)
        IQR = Q3 - Q1
        
        lower_bound = Q1 - (multiplier * IQR)
        upper_bound = Q3 + (multiplier * IQR)
        
        group['iqr_lower'] = lower_bound
        group['iqr_upper'] = upper_bound
        group['method_anomaly'] = (group['normalized_consumption'] < lower_bound) | (group['normalized_consumption'] > upper_bound)
        
        return group
    
    def apply_comparative_detection(group, threshold):
        """Karşılaştırmalı anomali tespiti"""
        mean = group['normalized_consumption'].mean()
        
        group['deviation_percent'] = np.abs((group['normalized_consumption'] - mean) / mean * 100)
        group['method_anomaly'] = group['deviation_percent'] > threshold
        
        return group
    
    # Seçilen yöntemi uygula
    if detection_method == "Standart Sapma (Z-Score)":
        df_analysis = df_work.groupby('facility_id', group_keys=False).apply(
            lambda x: apply_zscore_detection(x, threshold)
        )
        method_name = f"Z-Score (Eşik: {threshold})"
    
    elif detection_method == "IQR (Çeyrekler Arası)":
        df_analysis = df_work.groupby('facility_id', group_keys=False).apply(
            lambda x: apply_iqr_detection(x, multiplier)
        )
        method_name = f"IQR (Çarpan: {multiplier})"
    
    else:
        df_analysis = df_work.groupby('facility_id', group_keys=False).apply(
            lambda x: apply_comparative_detection(x, comp_threshold)
        )
        method_name = f"Karşılaştırmalı (Eşik: {comp_threshold}%)"
    
    df_analysis['is_anomaly'] = df_analysis['method_anomaly']
    
    # ============ SONUÇLAR ============
    st.header("📈 Adım 4: Sonuçlar")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Toplam Veri Noktası", len(df_analysis))
    with col2:
        st.metric("🏢 Toplam Tesisat", df_analysis['facility_id'].nunique())
    with col3:
        anomalies_count = df_analysis[df_analysis['is_anomaly']].shape[0]
        st.metric("🚨 Anomali Sayısı", anomalies_count)
    with col4:
        anomaly_pct = (anomalies_count / len(df_analysis) * 100) if len(df_analysis) > 0 else 0
        st.metric("⚠️ Anomali Oranı", f"{anomaly_pct:.1f}%")
    
    st.markdown(f"**Kullanılan Yöntem:** {method_name}")
    
    # ============ ANOMALİ DETAYLARI ============
    st.subheader("🚨 Tespit Edilen Anomaliler")
    
    anomalies_df = df_analysis[df_analysis['is_anomaly']].copy().sort_values('normalized_consumption', ascending=False)
    
    if len(anomalies_df) > 0:
        # Filtreleme
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_facilities = st.multiselect(
                "Tesisat Filtrele",
                sorted(anomalies_df['facility_id'].unique()),
                default=sorted(anomalies_df['facility_id'].unique())[:5]
            )
        
        filtered_anomalies = anomalies_df[anomalies_df['facility_id'].isin(selected_facilities)]
        
        # Detaylı tablo
        display_df = filtered_anomalies[['facility_id', 'month_name', 'raw_consumption', 
                                         'days_reported', 'normalized_consumption']].copy()
        display_df.columns = ['Tesisat ID', 'Dönem', 'Ham Tüketim (m³)', 'Gün', 'Norm. Tüketim (30g)']
        display_df['Ham Tüketim (m³)'] = display_df['Ham Tüketim (m³)'].round(2)
        display_df['Norm. Tüketim (30g)'] = display_df['Norm. Tüketim (30g)'].round(2)
        
        st.dataframe(display_df, use_container_width=True)
        
        # Her anomaliyi detaylı göster
        st.subheader("📌 Anomali Detayları")
        
        for idx, row in filtered_anomalies.iterrows():
            with st.expander(f"🔍 {row['facility_id']} - {row['month_name']}"):
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.write("**Ham Tüketim**")
                    st.write(f"{row['raw_consumption']:.2f} m³")
                with col2:
                    st.write("**Raporlanan Gün**")
                    st.write(f"{row['days_reported']} gün")
                with col3:
                    st.write("**Norm. Tüketim**")
                    st.write(f"{row['normalized_consumption']:.2f} m³")
                with col4:
                    st.write("**Durum**")
                    st.error("🚨 ANOMALI")
                
                if detection_method == "Standart Sapma (Z-Score)":
                    st.write(f"**Z-Score Değeri:** {row['z_score']:.2f} (Eşik: {threshold})")
                elif detection_method == "Karşılaştırmalı Analiz":
                    st.write(f"**Sapma Yüzdesi:** {row['deviation_percent']:.1f}% (Eşik: {comp_threshold}%)")
    else:
        st.info("✅ Anomali tespit edilmedi!")
    
    # ============ GÖRSELLEŞTIRME ============
    st.header("📊 Adım 5: Görselleştirme")
    
    viz_type = st.tabs(["Tesisat Analizi", "Genel Dağılım", "Karşılaştırma"])
    
    with viz_type[0]:
        st.subheader("📈 Tesisat Detaylı Analizi")
        facilities = sorted(df_analysis['facility_id'].unique())
        selected_facility = st.selectbox("Tesisat Seç:", facilities, key="facility_select")
        
        facility_data = df_analysis[df_analysis['facility_id'] == selected_facility].sort_values('date')
        
        if len(facility_data) > 0:
            col1, col2 = st.columns(2)
            
            with col1:
                fig = go.Figure()
                
                normal_data = facility_data[~facility_data['is_anomaly']]
                anomaly_data = facility_data[facility_data['is_anomaly']]
                
                fig.add_trace(go.Scatter(
                    x=normal_data['month_name'],
                    y=normal_data['normalized_consumption'],
                    mode='lines+markers',
                    name='Normal Tüketim',
                    line=dict(color='blue', width=2),
                    marker=dict(size=10)
                ))
                
                if len(anomaly_data) > 0:
                    fig.add_trace(go.Scatter(
                        x=anomaly_data['month_name'],
                        y=anomaly_data['normalized_consumption'],
                        mode='markers',
                        name='Anomali',
                        marker=dict(color='red', size=15, symbol='diamond')
                    ))
                
                mean_val = facility_data['normalized_consumption'].mean()
                fig.add_hline(y=mean_val, line_dash="dash", line_color="green", 
                             annotation_text=f"Ortalama: {mean_val:.1f}")
                
                fig.update_layout(
                    title=f"Tesisat {selected_facility} - Tüketim Trendi",
                    xaxis_title="Dönem",
                    yaxis_title="Tüketim (m³)",
                    height=400,
                    hovermode='x unified'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                detail_data = facility_data[['month_name', 'raw_consumption', 'normalized_consumption', 'is_anomaly']].copy()
                detail_data['Durum'] = detail_data['is_anomaly'].apply(lambda x: '🚨 ANOMALI' if x else '✅ Normal')
                detail_data.columns = ['Dönem', 'Ham Tüketim', 'Norm. Tüketim', '_', 'Durum']
                detail_data = detail_data.drop('_', axis=1)
                detail_data['Ham Tüketim'] = detail_data['Ham Tüketim'].round(2)
                detail_data['Norm. Tüketim'] = detail_data['Norm. Tüketim'].round(2)
                
                st.dataframe(detail_data, use_container_width=True, hide_index=True)
    
    with viz_type[1]:
        st.subheader("📊 Genel Dağılım Analizi")
        
        fig = px.box(df_analysis, y='normalized_consumption', 
                    title="Tüm Tesisatlar - Tüketim Dağılımı",
                    labels={'normalized_consumption': 'Normalleştirilmiş Tüketim (m³)'})
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        
        fig2 = px.histogram(df_analysis, x='normalized_consumption', nbins=50,
                           title="Tüketim Dağılımı Histogramı",
                           labels={'normalized_consumption': 'Normalleştirilmiş Tüketim (m³)'})
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)
    
    with viz_type[2]:
        st.subheader("🔄 Dönem Karşılaştırması")
        
        period_stats = df_analysis.groupby('month_name').agg({
            'normalized_consumption': ['mean', 'min', 'max', 'std']
        }).round(2)
        
        fig = go.Figure()
        
        months_order = sorted(df_analysis['month_name'].unique())
        
        for month in months_order:
            month_data = df_analysis[df_analysis['month_name'] == month]['normalized_consumption']
            fig.add_trace(go.Box(y=month_data, name=month))
        
        fig.update_layout(
            title="Dönemlere Göre Tüketim Kutu Grafikleri",
            yaxis_title="Normalleştirilmiş Tüketim (m³)",
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # ============ RAPOR İNDİR ============
    st.header("💾 Adım 6: Rapor İndir")
    
    if st.button("📊 Excel Raporu Oluştur", key="create_report"):
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Anomaliler
            anomaly_export = df_analysis[df_analysis['is_anomaly']][
                ['facility_id', 'date', 'month_name', 'raw_consumption', 
                 'days_reported', 'normalized_consumption']
            ].sort_values('normalized_consumption', ascending=False)
            anomaly_export.to_excel(writer, sheet_name='Anomaliler', index=False)
            
            # Tüm Veriler
            all_export = df_analysis[['facility_id', 'date', 'month_name', 'raw_consumption',
                                      'days_reported', 'normalized_consumption', 'is_anomaly']]
            all_export.to_excel(writer, sheet_name='Tüm Veriler', index=False)
            
            # Özet İstatistikler
            summary = df_analysis.groupby('facility_id').agg({
                'normalized_consumption': ['count', 'mean', 'min', 'max', 'std']
            }).round(2)
            summary.to_excel(writer, sheet_name='Özet İstatistikler')
        
        output.seek(0)
        st.download_button(
            label="⬇️ Raporu İndir (Excel)",
            data=output.getvalue(),
            file_name=f"anomali_raporu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

else:
    st.info("👈 Başlamak için lütfen Excel dosyasını yükleyin")
