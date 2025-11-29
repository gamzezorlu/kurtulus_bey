import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import io

st.set_page_config(page_title="Tüketim Anomali Tespiti", layout="wide")
st.title("📊 Uzaktan Okumalı Sayaç - Tüketim Anomali Tespiti")

# Sidebar ayarları
st.sidebar.header("⚙️ Ayarlar")
tolerance_percent = st.sidebar.slider(
    "Tolerans Yüzdesi (%)", 
    min_value=1, 
    max_value=20, 
    value=5,
    help="Farkın normal kabul edileceği yüzde"
)

# Veri yükleme
st.header("1️⃣ Veri Yükleme")
st.info("Excel dosyanızda: Tesisatçı | 24.11.2025 | 30.11.2025 sütunları olmalıdır")

uploaded_file = st.file_uploader("Excel dosyasını yükleyin (.xlsx)", type=['xlsx', 'xls', 'csv'])

if uploaded_file:
    try:
        # Excel dosyasını oku
        if uploaded_file.name.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(uploaded_file, dtype=str)
        else:
            df = pd.read_csv(uploaded_file, dtype=str)
        
        st.subheader("📋 Yüklenen Veriler")
        st.dataframe(df.head(10), use_container_width=True)
        
        # Sütun adlarını temizle
        df.columns = df.columns.astype(str).str.strip()
        
        # Sütun seçimi
        st.subheader("2️⃣ Sütunları Tanımlayın")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            id_col = st.selectbox("Tesisatçı ID sütunu", df.columns, 
                                  help="Sayaç veya tesisatçı kimliği")
        
        with col2:
            week_col = st.selectbox("Tüketim Sütunu", 
                                    [c for c in df.columns if c != id_col],
                                    help="24 günlük tüketim verisi")
        
        with col3:
            billing_col = st.selectbox("Faturalama Tüketim Sütunu", 
                                       [c for c in df.columns if c not in [id_col, week_col]],
                                       help="30 günlük faturalama verisi")
        
        with col4:
            measured_day = st.number_input("Ölçüm Tarihi (gün)", min_value=1, max_value=31, value=24,
                                          help="Tüketim ne günü ölçülmüş? (24, 26, 27, vs)")
        
        if st.button("🔍 Anomali Analizi Başlat", type="primary"):
            
            # Veri hazırlama
            df_analysis = df[[id_col, week_col, billing_col]].copy()
            df_analysis.columns = ['meter_id', 'week_consumption', 'billing_consumption']
            
            # Sayısal türe dönüştür
            df_analysis['week_consumption'] = pd.to_numeric(df_analysis['week_consumption'], errors='coerce')
            df_analysis['billing_consumption'] = pd.to_numeric(df_analysis['billing_consumption'], errors='coerce')
            
            # Null değerleri kaldır
            df_analysis = df_analysis.dropna()
            
            # Ölçüm gününe göre tüketimini 30 güne normalize et
            df_analysis['week_consumption_normalized'] = df_analysis['week_consumption'] * (30 / measured_day)
            
            # Fark hesapla
            df_analysis['difference'] = df_analysis['billing_consumption'] - df_analysis['week_consumption_normalized']
            
            # Yüzde fark
            df_analysis['difference_percent'] = np.where(
                df_analysis['week_consumption_normalized'] != 0,
                (df_analysis['difference'] / df_analysis['week_consumption_normalized'] * 100).round(2),
                0
            )
            
            # Anomali tespiti
            df_analysis['is_anomaly'] = abs(df_analysis['difference_percent']) > tolerance_percent
            
            df_analysis['status'] = df_analysis.apply(
                lambda row: '⚠️ FAZLA' if row['difference'] > 0 and row['is_anomaly'] 
                else '⚠️ EKSİK' if row['difference'] < 0 and row['is_anomaly']
                else '✅ Normal', 
                axis=1
            )
            
            # İstatistikler
            st.header("📊 Analiz Sonuçları")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Toplam Sayaç", len(df_analysis))
            
            with col2:
                anomaly_count = df_analysis['is_anomaly'].sum()
                pct = (anomaly_count / len(df_analysis) * 100) if len(df_analysis) > 0 else 0
                st.metric("Anomali Sayısı", anomaly_count, f"{pct:.1f}%")
            
            with col3:
                avg_diff = df_analysis['difference_percent'].mean()
                st.metric("Ort. Fark", f"{avg_diff:.2f}%", delta=None)
            
            with col4:
                max_diff = df_analysis['difference_percent'].abs().max()
                st.metric("Max Fark", f"{max_diff:.2f}%")
            
            # Anomali tablosu
            st.subheader("⚠️ Anomali Tespit Edilen Sayaçlar")
            anomalies = df_analysis[df_analysis['is_anomaly']].sort_values('difference_percent', key=abs, ascending=False)
            
            if len(anomalies) > 0:
                display_df = anomalies[[
                    'meter_id', 'week_consumption', 'week_consumption_normalized', 'billing_consumption', 
                    'difference', 'difference_percent', 'status'
                ]].copy()
                
                display_df.columns = [
                    'Tesisatçı ID', f'Tüketim ({measured_day}gün)', 'Tüketim (30gün tahmin)', 'Faturalama (30gün)', 
                    'Fark', 'Fark %', 'Durum'
                ]
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.success("✅ Anomali tespit edilmedi! Tüm sayaçlar normal.")
            
            
           
            # Tüm veriler tablosu
            st.subheader("🔍 Tüm Veriler (Filtrelenebilir)")
            
            filter_status = st.multiselect(
                "Duruma göre filtrele",
                df_analysis['status'].unique(),
                default=df_analysis['status'].unique()
            )
            
            filtered_df = df_analysis[df_analysis['status'].isin(filter_status)].copy()
            filtered_df.columns = ['Tesisatçı ID', f'Tüketim ({measured_day}gün)', 'Tüketim (30gün tahmin)',
                                   'Faturalama', 'Fark', 'Fark %', 'Anomali', 'Durum']
            
            st.dataframe(filtered_df, use_container_width=True, height=400, hide_index=True)
            
            # EXCEL DOWNLOAD
            st.divider()
            st.subheader("📊 Verileri Excel Olarak İndir")
            
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                # Sheet 1: Anomaliler
                if len(anomalies) > 0:
                    anomalies_export = anomalies[[
                        'meter_id', 'week_consumption', 'week_consumption_normalized', 
                        'billing_consumption', 'difference', 'difference_percent', 'status'
                    ]].copy()
                    anomalies_export.columns = [
                        'Tesisatçı ID', f'Tüketim ({measured_day}gün)', 'Tüketim (30gün tahmin)', 
                        'Faturalama (30gün)', 'Fark', 'Fark %', 'Durum'
                    ]
                    anomalies_export.to_excel(writer, sheet_name='Anomaliler', index=False)
                
                # Sheet 2: Tüm Veriler
                all_export = df_analysis[[
                    'meter_id', 'week_consumption', 'week_consumption_normalized', 
                    'billing_consumption', 'difference', 'difference_percent', 'status'
                ]].copy()
                all_export.columns = [
                    'Tesisatçı ID', f'Tüketim ({measured_day}gün)', 'Tüketim (30gün tahmin)', 
                    'Faturalama (30gün)', 'Fark', 'Fark %', 'Durum'
                ]
                all_export.to_excel(writer, sheet_name='Tüm Veriler', index=False)
                
                # Sheet 3: Özet
                summary_data = {
                    'Metrik': [
                        'Toplam Sayaç',
                        'Anomali Sayısı',
                        'Anomali Yüzdesi (%)',
                        'Normal Sayaç',
                        'Fazla Anomali',
                        'Eksik Anomali',
                        'Ortalama Fark %',
                        'Max Fark %',
                        'Toplam Ölçüm Tüketimi',
                        'Toplam Tahmin Tüketimi',
                        'Toplam Faturalama',
                        'Toplam Fark'
                    ],
                    'Değer': [
                        len(df_analysis),
                        df_analysis['is_anomaly'].sum(),
                        f"{(df_analysis['is_anomaly'].sum() / len(df_analysis) * 100):.2f}%",
                        len(df_analysis[~df_analysis['is_anomaly']]),
                        len(fazla),
                        len(eksik),
                        f"{df_analysis['difference_percent'].mean():.2f}%",
                        f"{df_analysis['difference_percent'].abs().max():.2f}%",
                        f"{df_analysis['week_consumption'].sum():,.2f}",
                        f"{df_analysis['week_consumption_normalized'].sum():,.2f}",
                        f"{df_analysis['billing_consumption'].sum():,.2f}",
                        f"{df_analysis['difference'].sum():,.2f}"
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Özet', index=False)
            
            excel_buffer.seek(0)
            
            st.download_button(
                label="📥 TÜM VERİLERİ EXCEL OLARAK İNDİR",
                data=excel_buffer,
                file_name=f"tuketim_analizi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    except Exception as e:
        st.error(f"❌ Hata: {str(e)}")
        st.info("Lütfen dosya formatını kontrol edin ve tekrar deneyin.")

else:
    st.info("👈 Excel dosyasını yükleyerek başlayın")
    
    with st.expander("📚 Kullanım Talimatı"):
        st.write("""
        ### Adım 1: Excel Dosya Hazırlığı
        - Excel dosyasında 3 sütun olmalıdır:
          - **Sütun 1**: Tesisatçı/Sayaç ID
          - **Sütun 2**: Ölçüm Tüketimi (24, 26, 27 gün vs)
          - **Sütun 3**: 30 günlük Faturalama Tüketimi
        
        ### Adım 2: Dosya Yükleme
        - Excel dosyasını (.xlsx) yükleyin
        - Sütunları sistem tarafından tanımlanabilecek şekilde seçin
        
        ### Adım 3: Analiz
        - Ölçüm gününü seçin (24, 26, 27, vs)
        - Tolerans yüzdesini ayarlayın (varsayılan %5)
        - "Anomali Analizi Başlat" butonuna tıklayın
        
        ### Sonuçlar
        - **✅ Normal**: Fark tolerans aralığında
        - **⚠️ FAZLA**: Faturalama, ölçümden daha yüksek
        - **⚠️ EKSİK**: Faturalama, ölçümden daha düşük
        
        ### İndirme
        - 3 sheet içeren Excel dosyası indirebilirsiniz:
          1. **Anomaliler**: Sadece anomali tespit edilen sayaçlar
          2. **Tüm Veriler**: Bütün sayaçlar
          3. **Özet**: İstatistiksel özet
        """)
