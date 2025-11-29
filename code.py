import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from io import BytesIO
import warnings
warnings.filterwarnings('ignore')

st.set_page_config(page_title="Su Tüketim Anomali Analiz", layout="wide")

st.title("💧 Su Sayacı - Anomali Karşılaştırma Sistemi")
st.markdown("Excel'de yaptığın gibi: **Geçen Yıl, Önceki Ay, Geçen Ay, Bu Ay** karşılaştırması")
st.markdown("---")

# Sidebar - Threshold Ayarları
with st.sidebar:
    st.header("⚙️ Anomali Eşikleri (Dinamik)")
    
    st.subheader("📊 Yüzde Sapma Eşik (%)")
    pct_threshold = st.slider(
        "Sapma % nede alarm ver?",
        5, 100, 30,
        help="Örn: 30% = Geçen yıldan 30% daha az/çok tüketim = Anomali"
    )
    
    st.subheader("📏 Mutlak Değer Eşik (m³)")
    abs_threshold = st.slider(
        "Mutlak tüketim farkında alarm ver?",
        0, 5000, 100, 50,
        help="Örn: 100 = Fark 100 m³den fazlaysa = Anomali"
    )
    
    st.subheader("🎯 Risk Skoru Kombinasyonu")
    risk_method = st.radio(
        "Nasıl hesapla?",
        ["VEYA (En Az Biri)", "VE (Her İkisi de)", "Ağırlıklı Ortalaması"]
    )
    
    st.markdown("---")
    st.info(f"""
    **Örnekler:**
    
    100 → 20 m³ değişimi:
    - % Sapma: 80%
    - Mutlak: 80 m³
    - Sonuç: {'🚨' if pct_threshold <= 80 or abs_threshold <= 80 else '✅'}
    
    10000 → 8000 m³ değişimi:
    - % Sapma: 20%
    - Mutlak: 2000 m³
    - Sonuç: {'🚨' if pct_threshold <= 20 or abs_threshold <= 2000 else '✅'}
    """)

# Veri Yükleme
st.header("📁 Veri Yükleme")
uploaded_file = st.file_uploader("Excel dosyasını yükle", type=["xlsx", "xls"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    
    st.info(f"✅ {len(df)} tesisat, {len(df.columns)-1} dönem yüklendi")
    
    # Veri dönüştürme
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
    
    # Veriyi dönüştür (pivot)
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
    df_work = df_work.sort_values(['facility_id', 'date'])
    
    st.success("✅ Veriler hazırlandı!")
    
    # ============ KARŞILAŞTIRMA ============
    st.header("🔄 Dönem Karşılaştırması")
    
    # Her tesisat için karşılaştırma yap
    comparison_list = []
    
    for facility in df_work['facility_id'].unique():
        facility_data = df_work[df_work['facility_id'] == facility].sort_values('date')
        
        if len(facility_data) < 2:
            continue
        
        # En son dönemi (bu ay - kısmi veri)
        latest = facility_data.iloc[-1]
        
        # Geçen ayı bul
        prev_month = None
        if len(facility_data) >= 2:
            prev_month = facility_data.iloc[-2]
        
        # Geçen yılın aynı ayını bul
        same_month_last_year = None
        for row in facility_data.itertuples():
            if row.month == latest.month and row.year == latest.year - 1:
                same_month_last_year = row
        
        # 2 ay öncesini bul (iki önceki ay)
        month_2_ago = None
        if len(facility_data) >= 3:
            month_2_ago = facility_data.iloc[-3]
        
        # Karşılaştırma yap
        comp_dict = {
            'facility_id': facility,
            'current_date': latest.date,
            'current_month': latest.month_name,
            'current_raw': latest.raw_consumption,
            'current_normalized': latest.normalized_consumption,
            'current_days': latest.days_reported,
        }
        
        # Referans değer olarak normalleştirilmiş değeri kullan
        reference_value = latest.normalized_consumption
        
        # Geçen yılın aynı ayı ile karşılaştır
        if same_month_last_year is not None:
            comp_dict['last_year_same_month'] = same_month_last_year.normalized_consumption
            comp_dict['last_year_date'] = same_month_last_year.date
            comp_dict['diff_last_year_pct'] = abs(latest.normalized_consumption - same_month_last_year.normalized_consumption) / (same_month_last_year.normalized_consumption + 0.001) * 100
            comp_dict['diff_last_year_abs'] = abs(latest.normalized_consumption - same_month_last_year.normalized_consumption)
        else:
            comp_dict['last_year_same_month'] = None
            comp_dict['last_year_date'] = None
            comp_dict['diff_last_year_pct'] = None
            comp_dict['diff_last_year_abs'] = None
        
        # Geçen ay ile karşılaştır
        if prev_month is not None:
            comp_dict['prev_month'] = prev_month.normalized_consumption
            comp_dict['prev_month_date'] = prev_month.date
            comp_dict['diff_prev_month_pct'] = abs(latest.normalized_consumption - prev_month.normalized_consumption) / (prev_month.normalized_consumption + 0.001) * 100
            comp_dict['diff_prev_month_abs'] = abs(latest.normalized_consumption - prev_month.normalized_consumption)
        else:
            comp_dict['prev_month'] = None
            comp_dict['prev_month_date'] = None
            comp_dict['diff_prev_month_pct'] = None
            comp_dict['diff_prev_month_abs'] = None
        
        # 2 ay öncesi ile karşılaştır
        if month_2_ago is not None:
            comp_dict['month_2_ago'] = month_2_ago.normalized_consumption
            comp_dict['month_2_ago_date'] = month_2_ago.date
            comp_dict['diff_month_2ago_pct'] = abs(latest.normalized_consumption - month_2_ago.normalized_consumption) / (month_2_ago.normalized_consumption + 0.001) * 100
            comp_dict['diff_month_2ago_abs'] = abs(latest.normalized_consumption - month_2_ago.normalized_consumption)
        else:
            comp_dict['month_2_ago'] = None
            comp_dict['month_2_ago_date'] = None
            comp_dict['diff_month_2ago_pct'] = None
            comp_dict['diff_month_2ago_abs'] = None
        
        comparison_list.append(comp_dict)
    
    df_comparison = pd.DataFrame(comparison_list)
    
    # ============ ANOMALİ MARKAJ ============
    
    def check_anomaly(row, threshold_pct, threshold_abs, method):
        """Anomali kontrolü yap"""
        anomaly_flags = []
        anomaly_reason = []
        
        # Geçen yılla karşılaştır
        if row['diff_last_year_pct'] is not None:
            is_anom_pct = row['diff_last_year_pct'] > threshold_pct
            is_anom_abs = row['diff_last_year_abs'] > threshold_abs
            
            if is_anom_pct:
                anomaly_reason.append(f"Geçen yıldan {row['diff_last_year_pct']:.1f}%")
            if is_anom_abs:
                anomaly_reason.append(f"Geçen yıldan {row['diff_last_year_abs']:.1f}m³")
            
            if method == "VEYA (En Az Biri)":
                anomaly_flags.append(is_anom_pct or is_anom_abs)
            elif method == "VE (Her İkisi de)":
                anomaly_flags.append(is_anom_pct and is_anom_abs)
            else:
                combined = (row['diff_last_year_pct'] + row['diff_last_year_abs'] / 10) / 2
                anomaly_flags.append(combined > (threshold_pct + threshold_abs / 10) / 2)
        
        # Geçen ay ile karşılaştır
        if row['diff_prev_month_pct'] is not None:
            is_anom_pct = row['diff_prev_month_pct'] > threshold_pct
            is_anom_abs = row['diff_prev_month_abs'] > threshold_abs
            
            if is_anom_pct:
                anomaly_reason.append(f"Geçen aydan {row['diff_prev_month_pct']:.1f}%")
            if is_anom_abs:
                anomaly_reason.append(f"Geçen aydan {row['diff_prev_month_abs']:.1f}m³")
            
            if method == "VEYA (En Az Biri)":
                anomaly_flags.append(is_anom_pct or is_anom_abs)
            elif method == "VE (Her İkisi de)":
                anomaly_flags.append(is_anom_pct and is_anom_abs)
            else:
                combined = (row['diff_prev_month_pct'] + row['diff_prev_month_abs'] / 10) / 2
                anomaly_flags.append(combined > (threshold_pct + threshold_abs / 10) / 2)
        
        # 2 ay öncesiyle karşılaştır
        if row['diff_month_2ago_pct'] is not None:
            is_anom_pct = row['diff_month_2ago_pct'] > threshold_pct
            is_anom_abs = row['diff_month_2ago_abs'] > threshold_abs
            
            if is_anom_pct:
                anomaly_reason.append(f"2 ay öncesinden {row['diff_month_2ago_pct']:.1f}%")
            if is_anom_abs:
                anomaly_reason.append(f"2 ay öncesinden {row['diff_month_2ago_abs']:.1f}m³")
            
            if method == "VEYA (En Az Biri)":
                anomaly_flags.append(is_anom_pct or is_anom_abs)
            elif method == "VE (Her İkisi de)":
                anomaly_flags.append(is_anom_pct and is_anom_abs)
            else:
                combined = (row['diff_month_2ago_pct'] + row['diff_month_2ago_abs'] / 10) / 2
                anomaly_flags.append(combined > (threshold_pct + threshold_abs / 10) / 2)
        
        is_anomaly = any(anomaly_flags) if anomaly_flags else False
        
        return is_anomaly, ", ".join(anomaly_reason) if anomaly_reason else "Normal"
    
    # Anomali kontrol et
    df_comparison['is_anomaly'] = df_comparison.apply(
        lambda row: check_anomaly(row, pct_threshold, abs_threshold, risk_method)[0],
        axis=1
    )
    df_comparison['anomaly_reason'] = df_comparison.apply(
        lambda row: check_anomaly(row, pct_threshold, abs_threshold, risk_method)[1],
        axis=1
    )
    
    # ============ SONUÇLAR ============
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📊 Toplam Tesisat", len(df_comparison))
    with col2:
        st.metric("🚨 Anomali Sayısı", df_comparison['is_anomaly'].sum())
    with col3:
        st.metric("✅ Normal Sayısı", (~df_comparison['is_anomaly']).sum())
    with col4:
        anomaly_pct = (df_comparison['is_anomaly'].sum() / len(df_comparison) * 100) if len(df_comparison) > 0 else 0
        st.metric("⚠️ Anomali Oranı", f"{anomaly_pct:.1f}%")
    
    # ============ ANOMALİ TABLOSU ============
    st.subheader("🚨 Tespit Edilen Anomaliler")
    
    anomalies = df_comparison[df_comparison['is_anomaly']].sort_values('current_raw', ascending=False)
    
    if len(anomalies) > 0:
        # Detaylı tablo
        display_data = []
        for idx, row in anomalies.iterrows():
            display_data.append({
                'Tesisat': row['facility_id'],
                'Bu Ay (m³)': f"{row['current_normalized']:.2f}",
                'Geçen Yıl': f"{row['last_year_same_month']:.2f}" if row['last_year_same_month'] else "N/A",
                'Sapm. %': f"{row['diff_last_year_pct']:.1f}%" if row['diff_last_year_pct'] else "-",
                'Sapm. m³': f"{row['diff_last_year_abs']:.1f}" if row['diff_last_year_abs'] else "-",
                'Neden': row['anomaly_reason'],
                'Durum': '🚨 ANOMALI'
            })
        
        display_df = pd.DataFrame(display_data)
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    else:
        st.info("✅ Anomali tespit edilmedi!")
    
    # ============ DETAYLI GÖRÜNÜM ============
    st.subheader("📋 Tüm Tesisatlar - Yan Yana Karşılaştırma")
    
    # Filtre
    show_all = st.checkbox("Tümünü göster", value=False)
    
    if show_all:
        display_full = df_comparison.copy()
    else:
        display_full = anomalies.copy()
    
    # Tablo
    table_data = []
    for idx, row in display_full.iterrows():
        status = "🚨 ANOMALI" if row['is_anomaly'] else "✅ NORMAL"
        
        table_data.append({
            'Tesisat': row['facility_id'],
            'Durum': status,
            'Bu Ay\n(30g norm.)': f"{row['current_normalized']:.1f}",
            'Bu Ay\n(Ham)': f"{row['current_raw']:.1f}",
            'Geçen Yıl\nAynı Ay': f"{row['last_year_same_month']:.1f}" if row['last_year_same_month'] else "-",
            'Fark %\n(Geçen Yıl)': f"{row['diff_last_year_pct']:.1f}%" if row['diff_last_year_pct'] else "-",
            'Fark m³\n(Geçen Yıl)': f"{row['diff_last_year_abs']:.1f}" if row['diff_last_year_abs'] else "-",
            'Geçen Ay': f"{row['prev_month']:.1f}" if row['prev_month'] else "-",
            'Fark %\n(Geçen Ay)': f"{row['diff_prev_month_pct']:.1f}%" if row['diff_prev_month_pct'] else "-",
        })
    
    table_df = pd.DataFrame(table_data)
    st.dataframe(table_df, use_container_width=True, hide_index=True)
    
    # ============ RAPOR İNDİR ============
    st.header("💾 Rapor İndir")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📊 Anomaliler - Excel"):
            export_df = anomalies[[
                'facility_id', 'current_month', 'current_raw', 'current_normalized',
                'last_year_same_month', 'diff_last_year_pct', 'diff_last_year_abs',
                'prev_month', 'diff_prev_month_pct', 'anomaly_reason'
            ]].copy()
            export_df.columns = [
                'Tesisat', 'Dönem', 'Ham Tüketim', 'Norm. Tüketim (30g)',
                'Geçen Yıl', 'Sapma %', 'Sapma m³', 'Geçen Ay', 'Sapma %', 'Neden'
            ]
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                export_df.to_excel(writer, sheet_name='Anomaliler', index=False)
                df_comparison.to_excel(writer, sheet_name='Tüm Veriler', index=False)
            
            output.seek(0)
            st.download_button(
                label="⬇️ Anomaliler (Excel)",
                data=output.getvalue(),
                file_name=f"anomaliler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
    with col2:
        if st.button("📊 Tüm Veriler - Excel"):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_comparison.to_excel(writer, sheet_name='Karşılaştırma', index=False)
                df_work.to_excel(writer, sheet_name='Ham Veriler', index=False)
            
            output.seek(0)
            st.download_button(
                label="⬇️ Tüm Veriler (Excel)",
                data=output.getvalue(),
                file_name=f"tum_veriler_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

else:
    st.info("👈 Başlamak için Excel dosyasını yükleyin")
